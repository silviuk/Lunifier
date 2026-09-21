import importlib
import inspect
import pkgutil
import typing
import lunifier


def test_all_type_annotations_valid():
    """Verify that all type annotations in lunifier resolve without NameError across any Python runtime."""
    errors = []
    for mod_info in pkgutil.walk_packages(lunifier.__path__, lunifier.__name__ + '.'):
        mod = importlib.import_module(mod_info.name)
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if inspect.isclass(attr) and attr.__module__ == mod.__name__:
                try:
                    typing.get_type_hints(attr)
                except Exception as e:
                    errors.append(f"Class {attr.__name__} in {mod.__name__}: {e}")
                for m_name, m_val in inspect.getmembers(attr, predicate=inspect.isfunction):
                    try:
                        typing.get_type_hints(m_val)
                    except Exception as e:
                        errors.append(f"Method {attr.__name__}.{m_name} in {mod.__name__}: {e}")
            elif inspect.isfunction(attr) and attr.__module__ == mod.__name__:
                try:
                    typing.get_type_hints(attr)
                except Exception as e:
                    errors.append(f"Function {attr.__name__} in {mod.__name__}: {e}")

    assert not errors, f"Type hint evaluation errors found: {errors}"
