from setuptools import setup


setup(
    name="portable-python",
    setup_requires="setupmeta",
    versioning="dev",
    author="Zoran Simic zoran@simicweb.com",
    keywords="python, portable, binary",
    url="https://github.com/codrsquad/portable-python",
    python_requires='>=3.6',
    entry_points={
        "console_scripts": [
            "portable-python = portable_python.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Installation/Setup",
        "Topic :: System :: Software Distribution",
        "Topic :: Utilities",
    ],
    project_urls={
        "Documentation": "https://github.com/codrsquad/portable-python/wiki",
        "Release notes": "https://github.com/codrsquad/portable-python/wiki/Release-notes",
        "Source": "https://github.com/codrsquad/portable-python",
    },
)
