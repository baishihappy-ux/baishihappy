from pathlib import Path

from python.engine.batch import recover_remaining_inputs


def main(batch_root=".", output_dir_name="姹囨€?):
    return recover_remaining_inputs(Path(batch_root).resolve(), output_dir_name)


