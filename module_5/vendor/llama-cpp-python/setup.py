from setuptools import find_packages, setup

setup(
    name="llama_cpp_python",
    version="0.3.35.post1",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "llama_cpp": ["lib/*"],
    },
    install_requires=[
        "typing-extensions>=4.5.0",
        "numpy>=1.20.0",
        "jinja2>=2.11.3",
    ],
)
