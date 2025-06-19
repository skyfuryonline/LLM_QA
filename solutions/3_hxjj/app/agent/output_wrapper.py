import os
import re
import tempfile
import uuid
from typing import Dict

import json
import numpy as np
import requests
from PIL import Image
from requests.exceptions import RequestException


class OutputWrapper:
    """
    Wrapper for output of tool execution when output is image, video, audio, etc.
    In this wrapper, __repr__() is implemented to return the str representation of the output for llm.
    Each wrapper have below attributes:
        path: the path where the output is stored
        raw_data: the raw data, e.g. image, video, audio, etc. In remote mode, it should be None
    """

    def __init__(self) -> None:
        self._repr = None
        self._path = None
        self._raw_data = None

        self.root_path = os.environ.get('OUTPUT_FILE_DIRECTORY', None)
        if self.root_path and not os.path.exists(self.root_path):
            try:
                os.makedirs(self.root_path)
            except Exception:
                self.root_path = None

    def get_remote_file(self, remote_path, suffix):
        try:
            response = requests.get(remote_path)
            obj = response.content
            directory = tempfile.mkdtemp(dir=self.root_path)
            path = os.path.join(directory, str(uuid.uuid4()) + f'.{suffix}')
            with open(path, 'wb') as f:
                f.write(obj)
            return path
        except RequestException:
            return remote_path

    def __repr__(self) -> str:
        return self._repr

    @property
    def path(self):
        return self._path

    @property
    def raw_data(self):
        return self._raw_data


class ImageWrapper(OutputWrapper):
    """
    Image wrapper, raw_data is a PIL.Image
    """

    def __init__(self, image) -> None:

        super().__init__()

        if isinstance(image, str):
            if os.path.isfile(image):
                self._path = image
            else:
                self._path = self.get_remote_file(image, 'png')
            try:
                image = Image.open(self._path)
                self._raw_data = image
            except FileNotFoundError:
                # Image store in remote server when use remote mode
                raise FileNotFoundError(f'Invalid path: {image}')
        else:
            if not isinstance(image, Image.Image):
                image = Image.fromarray(image.astype(np.uint8))
                self._raw_data = image
            else:
                self._raw_data = image
            directory = tempfile.mkdtemp(dir=self.root_path)
            self._path = os.path.join(directory, str(uuid.uuid4()) + '.png')
            self._raw_data.save(self._path)

        self._repr = f'![IMAGEGEN]({self._path})'



def get_raw_output(exec_result: Dict):
    # get rwa data of exec_result
    res = {}
    for k, v in exec_result.items():
        if isinstance(v, OutputWrapper):
            # In remote mode, raw data maybe None
            res[k] = v.raw_data or str(v)
        else:
            res[k] = v
    return res


def display(llm_result: str, exec_result: Dict, idx: int):
    """Display the result of each round in jupyter notebook.
    The multi-modal data will be extracted.

    Args:
        llm_result (str): llm result
        exec_result (Dict): exec result
        idx (int): current round
    """
    from IPython.display import display, Pretty, Image, Audio, JSON
    idx_info = '*' * 50 + f'round {idx}' + '*' * 50
    display(Pretty(idx_info))

    match_action = re.search(
        r'<\|startofthink\|>```JSON([\s\S]*)```<\|endofthink\|>', llm_result)
    if match_action:
        result = match_action.group(1)
        try:
            json_content = json.loads(result, strict=False)
            display(JSON(json_content))
            llm_result = llm_result.replace(match_action.group(0), '')
        except Exception:
            pass

    display(Pretty(llm_result))

    exec_result = exec_result.get('result', '')

    if isinstance(exec_result, dict):
        display(JSON(exec_result))
    else:
        display(Pretty(exec_result))

    return
