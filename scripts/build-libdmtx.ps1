# Builds libdmtx 0.7.4 as a 64-bit Windows DLL from official source, using the
# autotools + MinGW-w64 toolchain (the only supported build system for 0.7.4 —
# CMake was introduced later, in 0.7.7). The result is `libdmtx-64.dll`, which
# is what pylibdmtx.dmtx_library.load() and CZ_Decoder_build.spec both expect.
#
# Why pin 0.7.4 exactly: pylibdmtx selects its ctypes layout by libdmtx version
# (wrapper.py branches on `LooseVersion(dmtxVersion()) < 0.7.5`). A mismatched
# native runtime caused an access violation in the past, so the tag AND the
# exact upstream commit SHA are pinned, and HEAD is verified after checkout.
#
# The DLL is built with a static MinGW runtime (`-static-libgcc`; libdmtx is
# pure C, so no libstdc++), the MinGW equivalent of MSVC /MT, so the frozen EXE
# does not require additional runtime DLLs on the target machine.
param(
    [string]$Version = "0.7.4",
    [string]$CommitSha = "eba6d5193fff75efa2707d0c0a5ded9134d2aa58"
)

$ErrorActionPreference = "Stop"

# --- Locate MSYS2 (pre-installed on GH Windows runners at C:\msys64).
$msysBash = "C:\msys64\usr\bin\bash.exe"
$msysPacman = "C:\msys64\usr\bin\pacman.exe"
if (-not (Test-Path $msysBash)) {
    throw "MSYS2 bash not found at $msysBash"
}
if (-not (Test-Path $msysPacman)) {
    throw "MSYS2 pacman not found at $msysPacman"
}

# --- Work dir (Windows path -> MSYS path done inside the bash script).
$workWin = Join-Path $env:RUNNER_TEMP ("libdmtx-" + $Version)
if (Test-Path $workWin) {
    Remove-Item -Recurse -Force $workWin
}
New-Item -ItemType Directory -Force -Path $workWin | Out-Null

# Convert the Windows work dir to an MSYS path for use inside bash.
# (Runner temp is like C:\Users\runneradmin\AppData\Local\Temp\...)
$workUnix = (& $msysBash -lc "cygpath -u '$($workWin -replace '\\','/')'").Trim()
if (-not $workUnix) {
    throw "Failed to resolve MSYS path for $workWin"
}
Write-Host "Work dir (MSYS) : $workUnix"

# --- Install MinGW-w64 x64 toolchain + autotools (idempotent; pinned upstream).
#     `mingw-w64-x86_64-autotools` meta pulls autoconf/automake/libtool/make.
Write-Host "Installing MSYS2 MinGW-w64 x64 toolchain + autotools..."
& $msysBash -lc "pacman -S --noconfirm --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-autotools"
if ($LASTEXITCODE -ne 0) {
    throw "pacman install failed (exit $LASTEXITCODE)"
}

# --- Build script (run inside the MINGW64 environment via bash -lc).
#     MINGW64 tools are under /mingw64/bin; we prepend to PATH.
$buildScript = @"
set -euo pipefail
export PATH="/mingw64/bin:\$PATH"
set -x

cd "$workUnix"

git clone --quiet https://github.com/dmtx/libdmtx.git src
cd src
git checkout --quiet $CommitSha

# Verify HEAD matches the pinned commit exactly.
head_sha="\$(git rev-parse HEAD)"
if [ "\$head_sha" != "$CommitSha" ]; then
  echo "HEAD mismatch: expected $CommitSha, got \$head_sha" >&2
  exit 1
fi
echo "Checked out libdmtx at \$head_sha (v$Version)"

# Generate configure (autogen.sh — simply runs autoreconf).
if [ -x ./autogen.sh ]; then
  ./autogen.sh
else
  autoreconf -fi
fi

# Configure for the MinGW-w64 x64 host (build shared, per upstream README).
./configure --host=x86_64-w64-mingw32 --disable-static --enable-shared

# Build. libtool produces the shared DLL (e.g. .libs/libdmtx-0.dll or a
# libtool-managed dmtx.dll) under MinGW.
make -j"\$(nproc)"

# If libtool did not already emit a dmtx.dll, assemble one by hand (the
# upstream README.mingw path), with a static MinGW runtime so the DLL carries
# no extra runtime dependencies.
if [ ! -f dmtx.dll ] && [ ! -f .libs/dmtx.dll ]; then
  mkdir -p dll
  gcc -shared -o dll/dmtx.dll -static-libgcc .libs/*.o
  mv dll/dmtx.dll dmtx.dll 2>/dev/null || true
fi

ls -la .  .libs/ 2>/dev/null || true
"@

$buildScriptPath = Join-Path $workWin "build.sh"
# Write with LF line endings for bash.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($buildScriptPath, $buildScript, $utf8NoBom)

# Run; feed the MSYS path to the script.
$buildScriptUnix = (& $msysBash -lc "cygpath -u '$($buildScriptPath -replace '\\','/')'").Trim()
& $msysBash -lc "bash '$buildScriptUnix'"
if ($LASTEXITCODE -ne 0) {
    throw "libdmtx build failed (exit $LASTEXITCODE)"
}

# --- Locate the produced DLL. libtool under MinGW may name it dmtx.dll,
#     libdmtx-0.dll, or place it in .libs/. Match any libdmtx/dmtx .dll.
$found = Get-ChildItem -Path $workWin -Recurse -Filter "*.dll" |
    Where-Object { $_.Name -match '^(libdmtx|dmtx)' } |
    Sort-Object { $_.Name.Length } |   # prefer the shortest/most canonical name
    Select-Object -First 1
if (-not $found) {
    throw "dmtx.dll was not produced"
}
$dllWin = $found.FullName
Write-Host "Built DLL  : $dllWin"

# --- Copy into the active interpreter's pylibdmtx package dir as libdmtx-64.dll.
$site = (python -c "import site,sys; print([p for p in site.getsitepackages()][0])").Trim()
$dstDir = Join-Path $site "pylibdmtx"
if (-not (Test-Path $dstDir)) {
    throw "pylibdmtx package dir missing: $dstDir"
}
$dst = Join-Path $dstDir "libdmtx-64.dll"
Copy-Item $dllWin $dst -Force
if (-not (Test-Path $dst)) {
    throw "Failed to place libdmtx-64.dll at $dst"
}
Write-Host "Placed DLL : $dst"

# --- Verify the runtime version is exactly 0.7.4 (pylibdmtx loads the DLL and
#     reports dmtxVersion(); this also exercises the ctypes layout selection).
$ver = (python -c "from pylibdmtx import wrapper; print(wrapper.dmtxVersion())").Trim()
Write-Host "dmtxVersion(): $ver"
if ($ver -ne "0.7.4") {
    throw "Pinned version is 0.7.4, but loaded libdmtx reports '$ver'"
}

Write-Host "libdmtx 0.7.4 build + placement + runtime check complete."
