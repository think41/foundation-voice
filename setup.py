from setuptools import setup

if __name__ == "__main__":
    # All configuration is now in pyproject.toml
    # setup.py is minimal for compatibility or if specific setuptools features
    # not yet supported by pyproject.toml are needed (not the case here).
    setup(
        # If you still want to specify some things here, ensure they don't conflict
        # with pyproject.toml. For modern packaging, pyproject.toml is preferred.
        # For example, explicitly enabling include_package_data if not relying on default:
        # include_package_data=True
    )
