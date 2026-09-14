"""Regression-тест на найденный баг: самописный _FakeLooseVersion ломал
выбор ctypes struct layout в pylibdmtx.

Причина бага: в cz_decoder.py был фейковый компаратор версий с
`__lt__ -> False`, из-за чего `LooseVersion('0.7.4') < LooseVersion('0.7.5')`
возвращало `False`, pylibdmtx ошибочно выбирал НОВЫЙ struct layout для СТАРОЙ
libdmtx 0.7.4 → access violation при `string_at(msg.contents.output)`.

Фикс: _ensure_distutils() теперь гарантирует НАСТОЯЩИЙ LooseVersion
(из встроенного distutils, либо реальный из setuptools._distutils.version),
и после shim'a обязано выполняться корректное сравнение версий.
"""


def test_ensure_distutils_provides_real_looseversion():
    """После _ensure_distutils() 'import distutils.version' даёт НАСТОЯЩИЙ
    LooseVersion, который корректно сравнивает версии."""
    import czdecoder.datamatrix as dm

    # Выполняем shim (идемпотентен).
    dm._ensure_distutils()

    from distutils.version import LooseVersion

    # Ключевое: сравнение должно быть ЧЕСТНЫМ, не константным.
    assert LooseVersion("0.7.4") < LooseVersion("0.7.5")
    assert not (LooseVersion("0.7.5") < LooseVersion("0.7.5"))
    assert LooseVersion("0.7.8") > LooseVersion("0.7.5")


def test_looseversion_is_not_fake():
    """Конкретно на баг: сравнение 0.7.4 < 0.7.5 обязано быть True,
    а 0.7.5 < 0.7.5 — False (фейковый компаратор возвращал False/True
    константно)."""
    import czdecoder.datamatrix as dm
    dm._ensure_distutils()

    from distutils.version import LooseVersion

    # Прямая проверка исходной проблемы (а не только через assert выше):
    assert (LooseVersion("0.7.4") < LooseVersion("0.7.5")) is True
    assert (LooseVersion("0.7.5") < LooseVersion("0.7.4")) is False


def test_ensure_distutils_does_not_mutate_existing_real_distutils():
    """Если distutils.version уже настоящий — shim не должен его ломать."""
    import czdecoder.datamatrix as dm
    dm._ensure_distutils()

    from distutils.version import LooseVersion
    # Санкционированное поведение остаётся корректным после повторного вызова.
    assert LooseVersion("1.0") < LooseVersion("2.0")
    assert LooseVersion("2.0") > LooseVersion("1.0")


def test_no_fake_looseversion_in_project():
    """Гарантируем, что _FakeLooseVersion больше нигде не остался в исходниках."""
    import pathlib

    marker = "_FakeLooseVersion"
    root = pathlib.Path(__file__).resolve().parent.parent
    this_file = pathlib.Path(__file__).resolve()
    for py in root.rglob("*.py"):
        # Пропускаем виртуальные окружения, кэши и сам тестовый файл
        # (в нём маркер упомянут только в docstring как описание бага).
        parts = set(py.parts)
        if any(seg in parts for seg in (".venv-test", ".venv", "__pycache__")):
            continue
        if py.resolve() == this_file:
            continue
        text = py.read_text(encoding="utf-8")
        assert marker not in text, (
            f"Найден остаток фейкового компаратора в {py}"
        )