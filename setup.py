from distutils.core import setup

setup(
    name="json_repair",
    packages=["json_repair"],
    version="0.1.0",
    license="MIT",
    description="A package to repair broken json strings. Particularly useful if you are using LLMs to generate JSON",
    author="STEFANO BACCIANELLA",
    author_email="4247706+mangiucugna@users.noreply.github.com",
    url="https://github.com/mangiucugna/json_repair/",
    download_url="https://github.com/mangiucugna/json_repair/archive/v0.1.0.tar.gz",
    keywords=["JSON", "REPAIR", "LLM", "PARSER"],
    install_requires=[],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
