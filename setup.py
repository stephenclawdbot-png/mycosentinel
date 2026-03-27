from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mycosentinel",
    version="0.1.0",
    author="MycoSentinel Research Consortium",
    author_email="research@mycosentinel.ai",
    description="Living biosensor network for environmental monitoring using engineered fungi",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/stephenclawdbot-png/mycosentinel",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.21.0",
        "pyyaml>=5.4.0",
    ],
    extras_require={
        "hardware": [
            "RPi.GPIO>=0.7.0;platform_machine=='armv7l' or platform_machine=='aarch64'",
            "picamera2>=0.3.0;platform_machine=='armv7l' or platform_machine=='aarch64'",
            "adafruit-circuitpython-ads1x15>=2.2.0",
        ],
        "ml": [
            "tensorflow>=2.8.0",
        ],
        "dashboard": [
            "fastapi>=0.75.0",
            "uvicorn>=0.17.0",
            "flask>=2.0.0",
            "flask-socketio>=5.1.0",
        ],
        "network": [
            "paho-mqtt>=1.6.0",
            "requests>=2.27.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "mycosentinel=mycosentinel.main:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
