# module to help mange calibration data

import json

CALIBARTION_FILE = 'calibration.json'

class Calibration:
    def __init__(self, file_path=CALIBARTION_FILE):
        self.file_path = file_path
        self.load_calibration()

    def load_calibration(self, file_name:str=None):
        self.data = {}
        if file_name is not None:
            self.file_path = file_name
        try:
            with open(self.file_path, 'r') as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            # File not found or invalid JSON
            self.data = {}

    def save_calibration(self, file_name:str=None):
        if file_name is None:
            file_name = self.file_path
        with open(file_name, 'w') as f:
            json.dump(self.data, f)
        print('## save calib ##')

    def get(self, key, default=None):
        """Get a calibration value by key."""
        if key not in self.data:
            self.data[key] = default
        return self.data[key]

    def set(self, key, value):
        """Set a calibration value."""
        self.data[key] = value
        # self._save_calibration()

    def delete(self, key):
        """Delete a calibration value."""
        if key in self.data:
            del self.data[key]
            # self._save_calibration()
            return True
        return False

    def __str__(self):
        return json.dumps(self.data)

# create singleton
calibration = Calibration()

