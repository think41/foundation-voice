from setuptools import setup, Extension
from setuptools.command.build_py import build_py as _build_py # Import original build_py
from Cython.Build import cythonize
import os
import glob

# The root directory of your package
package_name = "foundational_ai_server"

def get_extensions():
    extensions = []
    # Search for .py files recursively within the package directory
    # Path should be relative to setup.py
    file_pattern = os.path.join(package_name, "**", "*.py")
    
    for filepath in glob.glob(file_pattern, recursive=True):
        # Exclude __init__.py files
        if os.path.basename(filepath) == "__init__.py":
            continue
        
        # Convert filepath to module name
        module_name_parts = os.path.splitext(filepath)[0].split(os.sep)
        module_name = ".".join(module_name_parts)
        extensions.append(Extension(module_name, [filepath]))
        
    if not extensions:
        # Using single quotes for the f-string to simplify JSON escaping later if needed
        print(f'Warning: No .py files (excluding __init__.py) found to compile in "{package_name}".')
    return extensions

ext_modules_to_compile = get_extensions()

# Custom build_py command to exclude .py source files for compiled extensions
class build_py_cython(_build_py):
    def find_package_modules(self, package, package_dir):
        # Get the original list of modules
        modules = super().find_package_modules(package, package_dir)
        
        # Get the set of fully qualified names of all compiled extensions
        compiled_module_names = set()
        if self.distribution.ext_modules:
            for ext in self.distribution.ext_modules:
                compiled_module_names.add(ext.name)

        # Filter out .py files if a .so/.pyd extension exists for them
        filtered_modules = []
        for (pkg, module, filepath) in modules:
            # Construct the full module name based on how Extension names were created
            current_module_full_name = ".".join(os.path.splitext(filepath)[0].split(os.sep))

            if current_module_full_name not in compiled_module_names:
                filtered_modules.append((pkg, module, filepath))
            # else:
            #     print(f'Excluding source file {filepath} from wheel because "{current_module_full_name}" is compiled.')
        
        return filtered_modules

if __name__ == "__main__":
    setup(
        ext_modules=cythonize(
            ext_modules_to_compile,
            compiler_directives={'language_level': "3"},
        ) if ext_modules_to_compile else None,
        cmdclass={ # Add the custom build_py command
            'build_py': build_py_cython
        }
    )
