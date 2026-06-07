from setuptools import find_packages, setup


setup(
    name="guitarta",
    version="0.1.18",
    description="macOS guitar and bass practice app built with Python and Flet.",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.9",
    install_requires=[
        "flet[all]>=0.27.0",
        "flet-video>=0.1.0",
        "flet-audio>=0.1.0",
        "yt-dlp>=2025.10.14",
    ],
    entry_points={"console_scripts": ["guitarta=guitarta.main:main"]},
)
