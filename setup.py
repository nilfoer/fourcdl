import setuptools

with open("README.md", "r", encoding="UTF-8") as fh:
    long_description = fh.read()


setuptools.setup(
    name="4CDownloader",
    version="0.1",
    description="A script that downloads files from 4chan.org and organizes them",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    author="nilfoer",
    author_email="",
    license="MIT",
    keywords="script 4chan chan download scraping",
    packages=setuptools.find_packages(exclude=['tests*']),
    python_requires='>=3.6',
    install_requires=["pyperclip>=1.5.25,<=1.7.0", "beautifulsoup4>=4.5.3,<=4.6.3"],
    tests_require=['pytest'],
    # non-python data that should be included in the pkg
    # mapping from package name to a list of relative path names that should be copied into the package
    package_data={},
    entry_points={
        'console_scripts': [
            # linking the executable 4cdl here to running the python function main in the fourcdl module
            '4cdl=fourcdl.fourcdl:main',
        ]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)