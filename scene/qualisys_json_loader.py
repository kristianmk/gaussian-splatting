#
# First parts are based on:
# https://raw.githubusercontent.com/graphdeco-inria/gaussian-splatting/main/scene/colmap_loader.py
# (see copyright notice in that file).
#
# read_intrinsics_json, read_extrinsics_json, and tests: written by K. M. Knausgård 2024-01 (License: MIT)
#

import numpy as np
import collections
import json
import os
import re
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

CameraModel = collections.namedtuple(
    "CameraModel", ["model_id", "model_name", "num_params"])
Camera = collections.namedtuple(
    "Camera", ["id", "model", "width", "height", "params"])
BaseImage = collections.namedtuple(
    "Image", ["id", "qvec", "tvec", "camera_id", "name", "xys", "point3D_ids"])
Point3D = collections.namedtuple(
    "Point3D", ["id", "xyz", "rgb", "error", "image_ids", "point2D_idxs"])
CAMERA_MODELS = {
    CameraModel(model_id=0, model_name="SIMPLE_PINHOLE", num_params=3),
    CameraModel(model_id=1, model_name="PINHOLE", num_params=4),
    CameraModel(model_id=2, model_name="SIMPLE_RADIAL", num_params=4),
    CameraModel(model_id=3, model_name="RADIAL", num_params=5),
    CameraModel(model_id=4, model_name="OPENCV", num_params=8),
    CameraModel(model_id=5, model_name="OPENCV_FISHEYE", num_params=8),
    CameraModel(model_id=6, model_name="FULL_OPENCV", num_params=12),
    CameraModel(model_id=7, model_name="FOV", num_params=5),
    CameraModel(model_id=8, model_name="SIMPLE_RADIAL_FISHEYE", num_params=4),
    CameraModel(model_id=9, model_name="RADIAL_FISHEYE", num_params=5),
    CameraModel(model_id=10, model_name="THIN_PRISM_FISHEYE", num_params=12)
}
CAMERA_MODEL_IDS = dict([(camera_model.model_id, camera_model)
                         for camera_model in CAMERA_MODELS])
CAMERA_MODEL_NAMES = dict([(camera_model.model_name, camera_model)
                           for camera_model in CAMERA_MODELS])


def qvec2rotmat(qvec):
    return np.array([
        [1 - 2 * qvec[2] ** 2 - 2 * qvec[3] ** 2,
         2 * qvec[1] * qvec[2] - 2 * qvec[0] * qvec[3],
         2 * qvec[3] * qvec[1] + 2 * qvec[0] * qvec[2]],
        [2 * qvec[1] * qvec[2] + 2 * qvec[0] * qvec[3],
         1 - 2 * qvec[1] ** 2 - 2 * qvec[3] ** 2,
         2 * qvec[2] * qvec[3] - 2 * qvec[0] * qvec[1]],
        [2 * qvec[3] * qvec[1] - 2 * qvec[0] * qvec[2],
         2 * qvec[2] * qvec[3] + 2 * qvec[0] * qvec[1],
         1 - 2 * qvec[1] ** 2 - 2 * qvec[2] ** 2]])


def rotmat2qvec(R):
    Rxx, Ryx, Rzx, Rxy, Ryy, Rzy, Rxz, Ryz, Rzz = R.flat
    K = np.array([
        [Rxx - Ryy - Rzz, 0, 0, 0],
        [Ryx + Rxy, Ryy - Rxx - Rzz, 0, 0],
        [Rzx + Rxz, Rzy + Ryz, Rzz - Rxx - Ryy, 0],
        [Ryz - Rzy, Rzx - Rxz, Rxy - Ryx, Rxx + Ryy + Rzz]]) / 3.0
    eigvals, eigvecs = np.linalg.eigh(K)
    qvec = eigvecs[[3, 0, 1, 2], np.argmax(eigvals)]
    if qvec[0] < 0:
        qvec *= -1
    return qvec


class Image(BaseImage):
    def qvec2rotmat(self):
        return qvec2rotmat(self.qvec)



def sorted_image_files(directory):
    # Regex pattern to match image files and extract camera numbers
    pattern = re.compile(r'.*Miqus_(\d+)_.*\.png$')

    # List all files in the directory
    files = os.listdir(directory)

    # Filter and extract camera numbers
    images = []
    for file in files:
        match = pattern.match(file)
        if match:
            camera_number = int(match.group(1))
            images.append((camera_number, file))

    # Sort by camera number
    images.sort()

    # Extract sorted file names
    sorted_files = [file for _, file in images]

    return sorted_files


def read_intrinsics_json(path, camera_model_type="OPENCV"):
    """
    Written by K. M. Knausgård 2024-01
    Modified to handle both PINHOLE and OPENCV camera models.
    """
    cameras = {}
    with open(path, "r") as file:
        data = json.load(file)
        if camera_model_type not in CAMERA_MODEL_NAMES:
            raise ValueError(f"Unsupported camera model type: {camera_model_type}")

        model_id = CAMERA_MODEL_NAMES[camera_model_type].model_id

        for idx, cam in enumerate(data["Cameras"], start=1):
            width = cam["FovVideo"]["Right"]
            height = cam["FovVideo"]["Bottom"]

            if camera_model_type == "OPENCV":
                # Extract OPENCV model parameters
                params = np.array([
                    cam["Intrinsic"]["FocalLengthU"],
                    cam["Intrinsic"]["FocalLengthV"],
                    cam["Intrinsic"]["CenterPointU"],
                    cam["Intrinsic"]["CenterPointV"],
                    cam["Intrinsic"]["RadialDistortion1"],
                    cam["Intrinsic"]["RadialDistortion2"],
                    cam["Intrinsic"]["TangentalDistortion1"],
                    cam["Intrinsic"]["TangentalDistortion2"],
                    # Add more parameters if available and necessary
                ])
            elif camera_model_type == "PINHOLE":
                # Extract PINHOLE model parameters
                params = np.array([
                    cam["Intrinsic"]["FocalLengthU"],
                    cam["Intrinsic"]["FocalLengthV"],
                    cam["Intrinsic"]["CenterPointU"],
                    cam["Intrinsic"]["CenterPointV"],
                    # PINHOLE model usually has only these four parameters
                ])
            else:
                # Handle other camera models if necessary
                params = np.array([])  # Placeholder for other models

            cameras[idx] = Camera(id=idx, model=model_id, width=width, height=height, params=params)
    return cameras


def read_extrinsics_json(path):
    """
    Written by K. M. Knausgård 2024-01
    """

    images = {}
    with open(path, 'r') as file:
        data = json.load(file)
        for idx, cam in enumerate(data["Cameras"], start=1):
            # Extract the translation vector
            tvec = np.array([cam["Transform"]["x"], cam["Transform"]["y"], cam["Transform"]["z"]])

            # Extract and convert the rotation matrix to a quaternion (why not use the DCM directly?)
            R = np.array([
                [cam["Transform"]["r11"], cam["Transform"]["r12"], cam["Transform"]["r13"]],
                [cam["Transform"]["r21"], cam["Transform"]["r22"], cam["Transform"]["r23"]],
                [cam["Transform"]["r31"], cam["Transform"]["r32"], cam["Transform"]["r33"]]
            ])
            qvec = rotmat2qvec(R)

            # Since the JSON does not contain direct image references, we use placeholders
            image_id = idx  # Placeholder image ID, TODO(KMK): Use the actual image ID
            camera_id = idx  # Assuming each camera corresponds to one 'image' for now TODO(KMK).
            image_name = "Camera_{}".format(idx)  # Placeholder image name
            xys = np.empty((0, 2))  # Placeholder for 2D points as we don't have this data
            point3D_ids = np.empty(0)  # Placeholder for 3D point IDs

            images[image_id] = Image(
                id=image_id, qvec=qvec, tvec=tvec,
                camera_id=camera_id, name=image_name,
                xys=xys, point3D_ids=point3D_ids
            )
    return images


def test_qualisys_json_loader():
    # Define the directory and file name
    directory_name = 'qualisys_json_loader_test_data'
    file_name = 'Test_Recording_Qualisys_MoCap_Miqus_Hybrid_Motionlab_UniversityOfAgder_Norway_0001.json'

    # Join the directory and file name to create a path
    test_data_file_path = os.path.join(directory_name, file_name)

    # Test the read_intrinsics_json function
    intrinsics = read_intrinsics_json(test_data_file_path)
    print("Intrinsics Data:")
    for camera_id, camera in intrinsics.items():
        print(
            f"Camera ID: {camera_id}, Model: {camera.model}, Width: {camera.width}, Height: {camera.height}, Params: {camera.params}")

    # Test the read_extrinsics_json function
    extrinsics = read_extrinsics_json(test_data_file_path)
    print("\nExtrinsics Data:")
    for image_id, image in extrinsics.items():
        print(f"Image ID: {image_id}, QVec: {image.qvec}, TVec: {image.tvec}")


def visualize_cameras(images, arrow_length_mm=500):
    plt.figure()

    # Define a unit vector in the direction the camera is facing (along negative Z-axis)
    unit_vector = np.array([0, 0, -1])

    # Draw each camera
    for image_id, image in images.items():
        # Camera position (negative because extrinsics are camera-to-world)
        camera_pos = image.tvec

        # Draw camera position
        plt.scatter(camera_pos[0], camera_pos[1], c='r', marker='o')

        # Calculate the camera orientation using DCM
        camera_orientation = image.qvec2rotmat().T @ unit_vector

        # Calculate the end point of the orientation line (500 mm along the orientation vector)
        line_end = camera_pos[:2] + (arrow_length_mm * camera_orientation[:2])

        # Draw camera orientation line
        plt.plot([camera_pos[0], line_end[0]], [camera_pos[1], line_end[1]], 'b-')

    # Draw reference frame (coordinate axes)
    axis_length = 2 * arrow_length_mm  # Length of the reference frame axes
    plt.quiver(0, 0, axis_length, 0, color='red', angles='xy', scale_units='xy', scale=1)
    plt.quiver(0, 0, 0, axis_length, color='green', angles='xy', scale_units='xy', scale=1)

    # Set labels and show plot
    plt.xlabel('X axis (mm)')
    plt.ylabel('Y axis (mm)')
    plt.title('Camera Extrinsics Visualization (2D)')
    plt.axis('equal')
    plt.grid(True)
    plt.show()


def set_axes_equal(ax):
    """Set 3D plot axes to equal scale."""
    # Extract the current limits and ranges
    x_limits = ax.get_xlim3d()
    y_limits = ax.get_ylim3d()
    z_limits = ax.get_zlim3d()

    x_range = abs(x_limits[1] - x_limits[0])
    y_range = abs(y_limits[1] - y_limits[0])
    z_range = abs(z_limits[1] - z_limits[0])

    # Find the maximum range and calculate the extra 10% for padding
    max_range = max(x_range, y_range, z_range)
    padding = max_range * 0.1

    # Set the axis limits with the same scale and padding
    ax.set_xlim([x_limits[0] - padding, x_limits[1] + padding])
    ax.set_ylim([y_limits[0] - padding, y_limits[1] + padding])
    ax.set_zlim([0, z_range + padding])


def visualize_cameras_3d(images, arrow_length_mm=750):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Create a 'floor' grid at z=0
    #create_floor(ax, images, grid_size=arrow_length_mm)

    # Define axis lengths
    axis_length = arrow_length_mm

    # Draw reference frame axes
    # X-axis in red, Y-axis in green, Z-axis in blue
    ax.quiver(0, 0, 0, axis_length, 0, 0, color='red')
    ax.quiver(0, 0, 0, 0, axis_length, 0, color='green')
    ax.quiver(0, 0, 0, 0, 0, axis_length, color='blue')

    # Draw each camera
    for image_id, image in images.items():
        # Camera position
        camera_pos = image.tvec

        # Draw camera position
        ax.scatter(camera_pos[0], camera_pos[1], camera_pos[2], c='r', marker='o')

        # Calculate the camera orientation using DCM
        camera_orientation = image.qvec2rotmat().T @ np.array([0, 0, -1])

        # Calculate the end point of the orientation line (500 mm along the orientation vector)
        line_end = camera_pos + (arrow_length_mm * camera_orientation)

        # Draw camera orientation line
        ax.plot([camera_pos[0], line_end[0]],
                [camera_pos[1], line_end[1]],
                [camera_pos[2], line_end[2]], 'b-')


    ax.set_zlim(-500, ax.get_zlim()[1])

    # Set labels
    ax.set_xlabel('X axis (mm)')
    ax.set_ylabel('Y axis (mm)')
    ax.set_zlabel('Z axis (mm)')
    ax.set_aspect('equal')  # https://matplotlib.org/3.6.0/users/prev_whats_new/whats_new_3.6.0.html#equal-aspect-ratio-for-3d-plots
    ax.set_title('Camera Extrinsics Visualization (3D)')

    plt.show()


def create_floor(ax, images, grid_size):
    # Find the range for x and y axes from camera positions
    x_values = [image.tvec[0] for image in images.values()]
    y_values = [image.tvec[1] for image in images.values()]

    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)

    # Extend the range by a fraction of the grid size for padding (removed the * 1.1)
    x_min -= grid_size
    x_max += grid_size
    y_min -= grid_size
    y_max += grid_size

    # Create a grid of points
    X, Y = np.meshgrid(np.linspace(x_min, x_max, 50), np.linspace(y_min, y_max, 50))
    Z = np.zeros_like(X)

    # Plot the transparent plane
    ax.plot_surface(X, Y, Z, color='blue', alpha=0.4)

    # Plot the wireframe grid with less alpha and higher zorder
    ax.plot_wireframe(X, Y, Z, color='gray', alpha=0.5)




if __name__ == "__main__":
    # Run tests
    test_qualisys_json_loader()


    # Visualize cameras for test case

    # Load extrinsic data
    directory = 'qualisys_json_loader_test_data'
    extrinsic_file = os.path.join(directory, 'Test_Recording_Qualisys_MoCap_Miqus_Hybrid_Motionlab_UniversityOfAgder_Norway_0001.json')
    extrinsics = read_extrinsics_json(extrinsic_file)

    # Sort image files
    sorted_files = sorted_image_files(directory)

    # Create a new dictionary for images sorted by their file names
    sorted_images = {}
    for file in sorted_files:
        # Extract camera number from file name
        camera_number = int(re.search(r'Miqus_(\d+)_', file).group(1))
        if camera_number in extrinsics:
            sorted_images[camera_number] = extrinsics[camera_number]

    # Visualize cameras with sorted extrinsic parameters
    visualize_cameras(sorted_images)

    # Enable interactive mode for 3D visualization
    plt.ion()
    visualize_cameras_3d(sorted_images)

    # Keep the plot open
    plt.show(block=True)
