from setuptools import setup, find_packages

setup(
    name="soundcraftui16auxswitcher",
    version="0.0.1",
    description=("POC"),
    url="https://github.com/dhoessl/soundcraftui16auxswitcher.git",
    author="Dominic Hößl",
    author_email="dhoessl@dhoessl.de",
    license="GPL-v3",
    packages=find_packages(exclude=["docs", "docs.*"]),
    package_data={},
    include_package_data=True,
    install_requires=[
        "soundcraftui16mqtt_mixer @ git+https://github.com/dhoessl/soundcraftui16mqtt.git"
        ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
    ]
)
