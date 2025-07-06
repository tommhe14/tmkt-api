from setuptools import setup, find_packages

setup(
    name="tmkt_api",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "aiohttp",
        "beautifulsoup4",
        "cachetools",
    ],
)