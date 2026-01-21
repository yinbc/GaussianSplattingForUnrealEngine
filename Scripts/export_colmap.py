#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Export Gaussian Splatting PLY to COLMAP format
Converts PLY point cloud to COLMAP points3D format
"""

import os
import sys
import argparse
import numpy as np
from plyfile import PlyData
from read_write_model import Point3D, write_points3D_text, write_points3D_binary, write_model, Camera, Image

# SH0 coefficient (same as in GaussianSplattingPointCloud.cpp)
C0 = 0.28209479177387814


def linear_to_srgb(linear):
    """Convert linear RGB to sRGB"""
    srgb = np.where(linear <= 0.0031308,
                    12.92 * linear,
                    1.055 * np.power(linear, 1.0 / 2.4) - 0.055)
    return np.clip(srgb, 0.0, 1.0)


def sh0_to_rgb(sh_dc):
    """Convert SH0 coefficients to RGB (0-255)

    Reverse of the conversion in GaussianSplattingPointCloud.cpp:
    Color = SH_0 * f_dc + 0.5
    Then SRGBToLinear(Color)

    So to reverse:
    1. LinearToSRGB
    2. (color - 0.5) / SH_0 -> but we start from f_dc directly
    """
    # f_dc is already the SH0 coefficient
    # Convert to linear color: SH_0 * f_dc + 0.5
    linear_color = C0 * sh_dc + 0.5
    linear_color = np.clip(linear_color, 0.0, 1.0)

    # Convert to sRGB
    srgb_color = linear_to_srgb(linear_color)

    # Convert to 0-255 range
    rgb = (srgb_color * 255).astype(np.uint8)

    return rgb


def ply_to_colmap_points(ply_path, output_dir, format='bin', coordinate_transform='none'):
    """
    Convert PLY file to COLMAP points3D format

    Args:
        ply_path: Path to input PLY file
        output_dir: Directory for output COLMAP files
        format: 'bin' or 'txt'
        coordinate_transform: 'none' or 'ue_to_colmap' (reverse UE coordinate conversion)
    """
    print(f"Loading PLY file: {ply_path}")
    plydata = PlyData.read(ply_path)
    vertices = plydata['vertex']
    num_points = len(vertices)

    print(f"Number of points: {num_points}")

    # Extract positions
    positions = np.vstack([vertices['x'], vertices['y'], vertices['z']]).T

    # Extract colors (SH0 coefficients)
    sh_dc = np.vstack([vertices['f_dc_0'], vertices['f_dc_1'], vertices['f_dc_2']]).T

    # Convert SH0 to RGB
    colors_rgb = sh0_to_rgb(sh_dc)

    # Extract opacity if available (for error estimation)
    property_names = [p.name for p in vertices.properties]
    if 'opacity' in property_names:
        opacity = vertices['opacity']
        # Convert logistic opacity to probability: 1 / (1 + exp(-opacity))
        opacity_values = 1.0 / (1.0 + np.exp(-opacity))
        # Use inverse of opacity as error (higher opacity = lower error)
        errors = 1.0 - opacity_values
    else:
        # Default error value
        errors = np.ones(num_points) * 0.5

    # Apply coordinate transform if requested
    if coordinate_transform == 'ue_to_colmap':
        # Reverse the UE coordinate conversion from GaussianSplattingPointCloud.cpp
        # UE: Point.Position = 100 * FVector3f(Position.X, -Position.Z, -Position.Y)
        # So: PLY_X = UE_X / 100, PLY_Y = -UE_Z / 100, PLY_Z = -UE_Y / 100
        # But the input PLY is already in original coordinates, so check if it needs conversion
        print("Note: Coordinate transform 'ue_to_colmap' assumes input PLY is in original COLMAP coordinates")
        # No transform needed if PLY is already in COLMAP format

    # Create COLMAP Point3D objects
    points3D = {}
    for i in range(num_points):
        point3D_id = i + 1  # COLMAP IDs start from 1
        xyz = positions[i]
        rgb = colors_rgb[i]
        error = float(errors[i])

        # Empty track (no image associations)
        image_ids = np.array([], dtype=np.int32)
        point2D_idxs = np.array([], dtype=np.int32)

        points3D[point3D_id] = Point3D(
            id=point3D_id,
            xyz=xyz,
            rgb=rgb,
            error=error,
            image_ids=image_ids,
            point2D_idxs=point2D_idxs
        )

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Write points3D file
    ext = '.bin' if format == 'bin' else '.txt'

    if format == 'bin':
        output_path = os.path.join(output_dir, f'points3D{ext}')
        print(f"Writing binary COLMAP points3D to: {output_path}")
        write_points3D_binary(points3D, output_path)
    else:
        output_path = os.path.join(output_dir, f'points3D{ext}')
        print(f"Writing text COLMAP points3D to: {output_path}")
        write_points3D_text(points3D, output_path)

    print(f"Successfully exported {num_points} points to COLMAP format")

    return points3D


def create_dummy_cameras_images(output_dir, format='bin'):
    """
    Create dummy cameras.bin/txt and images.bin/txt for a complete COLMAP model
    This is useful if you need a complete COLMAP reconstruction structure
    """
    # Create a simple pinhole camera
    cameras = {
        1: Camera(
            id=1,
            model='SIMPLE_PINHOLE',
            width=1920,
            height=1080,
            params=np.array([1000.0, 960.0, 540.0])  # focal, cx, cy
        )
    }

    # Create a dummy image at origin
    images = {
        1: Image(
            id=1,
            qvec=np.array([1.0, 0.0, 0.0, 0.0]),  # Identity rotation
            tvec=np.array([0.0, 0.0, 0.0]),  # Origin
            camera_id=1,
            name='dummy.jpg',
            xys=np.empty((0, 2)),  # No 2D points
            point3D_ids=np.array([], dtype=np.int64)
        )
    }

    ext = '.bin' if format == 'bin' else '.txt'

    if format == 'bin':
        from read_write_model import write_cameras_binary, write_images_binary
        write_cameras_binary(cameras, os.path.join(output_dir, f'cameras{ext}'))
        write_images_binary(images, os.path.join(output_dir, f'images{ext}'))
    else:
        from read_write_model import write_cameras_text, write_images_text
        write_cameras_text(cameras, os.path.join(output_dir, f'cameras{ext}'))
        write_images_text(images, os.path.join(output_dir, f'images{ext}'))

    print(f"Created dummy cameras{ext} and images{ext}")

    return cameras, images


def main():
    parser = argparse.ArgumentParser(
        description='Export Gaussian Splatting PLY to COLMAP format'
    )
    parser.add_argument(
        'ply_path',
        help='Path to input PLY file (e.g., point_cloud.ply)'
    )
    parser.add_argument(
        'output_dir',
        help='Output directory for COLMAP files'
    )
    parser.add_argument(
        '--format',
        choices=['bin', 'txt'],
        default='bin',
        help='Output format: binary (.bin) or text (.txt) (default: bin)'
    )
    parser.add_argument(
        '--coordinate-transform',
        choices=['none', 'ue_to_colmap'],
        default='none',
        help='Coordinate system transform (default: none)'
    )
    parser.add_argument(
        '--create-dummy-camera',
        action='store_true',
        help='Create dummy cameras.bin and images.bin for a complete COLMAP model'
    )

    args = parser.parse_args()

    # Check input file exists
    if not os.path.exists(args.ply_path):
        print(f"Error: PLY file not found: {args.ply_path}", file=sys.stderr)
        sys.exit(1)

    # Convert PLY to COLMAP points3D
    points3D = ply_to_colmap_points(
        args.ply_path,
        args.output_dir,
        format=args.format,
        coordinate_transform=args.coordinate_transform
    )

    # Optionally create dummy cameras and images
    if args.create_dummy_camera:
        create_dummy_cameras_images(args.output_dir, format=args.format)
        print(f"\nCreated complete COLMAP model in: {args.output_dir}")
        print(f"Files: cameras{'.bin' if args.format == 'bin' else '.txt'}, "
              f"images{'.bin' if args.format == 'bin' else '.txt'}, "
              f"points3D{'.bin' if args.format == 'bin' else '.txt'}")
    else:
        print(f"\nCreated COLMAP points3D in: {args.output_dir}")
        print(f"File: points3D{'.bin' if args.format == 'bin' else '.txt'}")
        print("\nNote: Only points3D file was created. Use --create-dummy-camera "
              "to create a complete COLMAP model with cameras and images.")


if __name__ == '__main__':
    main()
