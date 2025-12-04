from setuptools import setup, find_packages

setup(
    name="thanos-store-operator",
    version="1.0.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "kubernetes>=28.1.0",
        "pyyaml>=6.0.1",
    ],
    python_requires=">=3.9",
)