from setuptools import find_packages, setup


setup(
    name="guitarta",
    version="2.0.0",
    description="Cross-platform guitar and bass practice app built with Python and Flet.",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    install_requires=[
        "demucs>=4.0.1",
        "flet[all]>=0.27.0,<0.86.0",
        "flet-video>=0.1.0,<0.86.0",
        "flet-audio>=0.1.0,<0.86.0",
        "imageio-ffmpeg>=0.6.0",
        "yt-dlp>=2025.10.14",
        "torchcodec>=0.14.0",
    ],
    entry_points={"console_scripts": ["guitarta=guitarta.main:main"]},
)
