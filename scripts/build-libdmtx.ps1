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
$cygpath = "C:\msys64\usr\bin\cygpath.exe"
if (-not (Test-Path $msysBash)) {
    throw "MSYS2 bash not found at $msysBash"
}
if (-not (Test-Path $msysPacman)) {
    throw "MSYS2 pacman not found at $msysPacman"
}
if (-not (Test-Path $cygpath)) {
    throw "MSYS2 cygpath not found at $cygpath"
}

# --- Work dir.
$workWin = Join-Path $env:RUNNER_TEMP ("libdmtx-" + $Version)
if (Test-Path $workWin) {
    Remove-Item -Recurse -Force $workWin
}
New-Item -ItemType Directory -Force -Path $workWin | Out-Null

# --- Checkout libdmtx source with the Windows git (guaranteed present on the
#     GH Windows runner). MSYS2 is used only as the build toolchain, so we do
#     not install an MSYS2 git and avoid PATH issues inside bash.
$srcWin = Join-Path $workWin "src"
git clone --quiet https://github.com/dmtx/libdmtx.git $srcWin
if ($LASTEXITCODE -ne 0) {
    throw "git clone failed (exit $LASTEXITCODE)"
}
git -C $srcWin checkout --quiet $CommitSha
if ($LASTEXITCODE -ne 0) {
    throw "git checkout failed (exit $LASTEXITCODE)"
}
$headSha = (git -C $srcWin rev-parse HEAD).Trim()
if ($headSha -ne $CommitSha) {
    throw "HEAD mismatch: expected $CommitSha, got $headSha"
}
Write-Host "Checked out libdmtx at $headSha (v$Version)"

# --- Convert Windows paths to MSYS paths using cygpath.exe directly (NOT via
#     bash: on the very first MSYS2 run, bash prints one-time initial-setup
#     text to stdout, which would pollute the captured path).
$workUnix = (& $cygpath -u $workWin).Trim()
if (-not $workUnix -or ($workUnix -split "`n").Count -ne 1) {
    throw "Failed to resolve a single MSYS path for ${workWin}: '$workUnix'"
}
Write-Host "Work dir (MSYS) : $workUnix"

# --- MSYS path of the source directory (cygpath directly, single-line).
$srcUnix = (& $cygpath -u $srcWin).Trim()
if (-not $srcUnix -or ($srcUnix -split "`n").Count -ne 1) {
    throw "Failed to resolve a single MSYS path for ${srcWin}: '$srcUnix'"
}

# --- Install MinGW-w64 x64 toolchain + autotools (idempotent; pinned upstream).
#     `mingw-w64-x86_64-autotools` meta pulls autoconf/automake/libtool/make.
Write-Host "Installing MSYS2 MinGW-w64 x64 toolchain + autotools..."
& $msysBash -lc "pacman -S --noconfirm --needed mingw-w64-x86_64-gcc mingw-w64-x86_64-autotools"
if ($LASTEXITCODE -ne 0) {
    throw "pacman install failed (exit $LASTEXITCODE)"
}

# --- Pass values into bash via environment variables (single-quoted here-string
#     below means PowerShell performs NO interpolation, so bash sees plain bash).
$env:LIBDMTX_WORK_UNIX   = $workUnix
$env:LIBDMTX_COMMIT_SHA  = $CommitSha
$env:LIBDMTX_VERSION     = $Version
$env:LIBDMTX_SRC_UNIX    = $srcUnix

# --- Build script (run inside the MINGW64 environment via bash -lc).
#     MINGW64 tools are under /mingw64/bin; we prepend to PATH.
$buildScript = @'
set -euo pipefail
export PATH="/mingw64/bin:$PATH"
set -x

cd "$LIBDMTX_SRC_UNIX"

# Generate configure (autogen.sh — simply runs autoreconf).
if [ -x ./autogen.sh ]; then
  ./autogen.sh
else
  autoreconf -fi
fi

# Configure for the MinGW-w64 x64 host (build shared, per upstream README).
./configure --host=x86_64-w64-mingw32 --disable-static --enable-shared

# Build. libtool produces the shared DLL (e.g. .libs/libdmtx-0.dll) under
# MinGW.
make -j"$(nproc)"

# Only if NO suitable DLL was produced at all, fall back to the manual
# gcc -shared assembly described in upstream README.mingw.
if ! find . -maxdepth 2 -type f \( -name 'dmtx.dll' -o -name 'libdmtx*.dll' \) | grep -q .; then
  echo "libtool produced no DLL; assembling dmtx.dll manually" >&2
  mkdir -p dll
  gcc -shared -o dll/dmtx.dll -static-libgcc .libs/*.o
  mv dll/dmtx.dll dmtx.dll 2>/dev/null || true
fi

ls -la . .libs/ 2>/dev/null || true
'@

$buildScriptPath = Join-Path $workWin "build.sh"
# Write with LF (Unix) line endings for bash, no BOM.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($buildScriptPath, $buildScript, $utf8NoBom)

# --- Debug: print the generated build.sh with line numbers (no secrets).
Write-Host "===== generated build.sh ====="
$i = 1
Get-Content $buildScriptPath | ForEach-Object {
    Write-Host ("{0,3}: {1}" -f $i, $_)
    $i++
}
Write-Host "=============================="

# --- Resolve the script's MSYS path (cygpath directly) and run it.
$buildScriptUnix = (& $cygpath -u $buildScriptPath).Trim()
if (-not $buildScriptUnix -or ($buildScriptUnix -split "`n").Count -ne 1) {
    throw "Failed to resolve a single MSYS path for ${buildScriptPath}: '$buildScriptUnix'"
}
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
