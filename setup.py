from setuptools import setup, find_packages

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()

setup(
    name="open-source-cai-pipecat-core",
    version="0.1.0",
    author="Aniket-think41",
    description="Core package for Open Source CAI Pipecat",
    url="https://github.com/Aniket-think41/Open-Source-CAI-Pipecat",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'cai-pipecat-core=main:main',
        ],
    },
    package_data={
        '': ['*.py', '*.txt', '*.md'],
    },
    include_package_data=True,
)
