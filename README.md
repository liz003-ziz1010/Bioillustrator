## Architecture

BioIllustrator is organized into several related components: the main SVG
editor, SVG cleanup tools, raster-to-vector conversion tools, and experimental
drawing utilities.

### SVG Editor

The main application is:

    BioIllustrator.py

It provides the SVG editing environment, including:

- SVG asset library
- Canvas and scene management
- Object selection
- SVG transformations
- Edit history / undo functionality
- SVG rendering through TkSVG
- Importing and managing SVG assets
- Exporting the finished scene

The editor maintains the SVG scene state and renders the objects on the
canvas.

### SVG Cleanup

The SVG cleanup workflow takes existing SVG files and removes unwanted
background information.

    SVG files
        ↓
    Background removal
        ↓
    Cleaned SVGs

The cleaned SVG files can then be used as assets in the editor.

### Raster-to-Vector Conversion

The repository contains two raster-to-vector conversion tools:

#### Contour vectorizer

    vectors.py

The contour vectorizer converts raster images into SVG representations based
on their contours.

#### Color vectorizer

    colors.py

The color vectorizer converts raster images into SVG representations while
preserving color regions.

The two vectorizers follow this general workflow:

    Raster image
        ↓
    Vectorizer
        ↓
    Generated SVG

The generated SVG files can subsequently be used as assets in BioIllustrator.

### Experimental Tools

The repository also contains experimental tools that were developed while
building the project.

#### Scene drawing tool

    drawing_tool.py

A separate tool for experimenting with scene/drawing functionality.

#### Cell shape creator

    main.py

An experimental tool for creating cell-shaped vector artwork.

These tools are separate from the main `BioIllustrator.py` application.
