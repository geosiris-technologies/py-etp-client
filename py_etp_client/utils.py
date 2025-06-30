__H5PY_MODULE_EXISTS__ = True

try:
    import h5py
except Exception:
    __H5PY_MODULE_EXISTS__ = False


# HDF5
if __H5PY_MODULE_EXISTS__:

    def h5_list_datasets(h5_file_path):
        """
        List all datasets in an HDF5 file.
        :param h5_file_path: Path to the HDF5 file
        :return: List of dataset names in the HDF5 file
        """
        res = []
        with h5py.File(h5_file_path, "r") as f:
            # Function to print the names of all datasets
            def list_datasets(name, obj):
                if isinstance(obj, h5py.Dataset):  # Check if the object is a dataset
                    res.append(name)

            # Visit all items in the HDF5 file and apply the list function
            f.visititems(list_datasets)
        return res
