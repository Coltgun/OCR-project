import os, site, sys
nvidia_subdirs = ['cublas','cuda_runtime','cudnn','cufft','curand','cusolver','cusparse','nvjitlink']
extra_paths = []
for sp in site.getsitepackages():
    for subdir in nvidia_subdirs:
        dll_dir = os.path.join(sp, 'nvidia', subdir, 'bin')
        if os.path.isdir(dll_dir):
            os.add_dll_directory(dll_dir)
            extra_paths.append(dll_dir)
if extra_paths:
    os.environ['PATH'] = os.pathsep.join(extra_paths) + os.pathsep + os.environ.get('PATH', '')
print(f"Registered {len(extra_paths)} dirs")
import importlib
mod = importlib.import_module('paddle')
print('paddle', mod.__version__)
