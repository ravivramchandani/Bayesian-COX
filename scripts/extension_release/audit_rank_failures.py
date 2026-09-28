#!/usr/bin/env python3
"""Write-once, resumable reconstruction of pre-fit synthetic-rank failures.

Run with the production lock's interpreter, as a separate process. This helper
does not call a scientific model's fit, optimizer, sampler, or evaluator.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
for _variable in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS',
                  'VECLIB_MAXIMUM_THREADS'):
    os.environ[_variable] = '1'

import numpy as np  # noqa: E402 - thread limits must precede numeric-library imports.
import pandas as pd  # noqa: E402 - thread limits must precede numeric-library imports.

CLASSIFICATION = 'post_hoc_failure_provenance'
RANK_MESSAGE = 'synthetic design is not full column rank'


def require(condition: bool, message: str) -> None:
    """Raise ``ValueError(message)`` when ``condition`` is false."""
    if not condition:
        raise ValueError(message)


def sha(data: bytes) -> str:
    """Return the SHA-256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    """Hash a regular, non-linked file and reject it if its stat signature changes during the read."""
    require(path.is_file() and not path.is_symlink(), f'missing or linked audit input: {path}')
    before = path.stat()
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            f'audit input changed during read: {path}')
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    """Return the SHA-256 of a value's compact, key-sorted JSON encoding."""
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'),
                          ensure_ascii=False, allow_nan=False).encode('utf-8'))


def json_bytes(value: Any) -> bytes:
    """Encode a value as indented, key-sorted UTF-8 JSON with a trailing newline."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + '\n').encode('utf-8')


def read_json(path: Path) -> tuple[dict[str, Any], str]:
    """Read a JSON file, confirming it did not change during the read; return the value and the file hash."""
    before = file_hash(path)
    value = json.loads(path.read_bytes())
    require(file_hash(path) == before, f'audit JSON changed during read: {path}')
    return value, before


def write_once(path: Path, payload: bytes) -> None:
    """Publish ``payload`` at ``path`` unless it already exists with identical bytes.

    The bytes are written to a temporary file and hard-linked into place, which
    never replaces an existing file. An existing or concurrently written file
    must have exactly the same hash, which makes the audit safe to resume.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not any(p.is_symlink() for p in path.parents), 'linked audit-output ancestor refused')
    if path.exists() or path.is_symlink():
        require(file_hash(path) == sha(payload), f'existing write-once artifact differs: {path}')
        return
    fd, name = tempfile.mkstemp(prefix='.failure-provenance-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)  # Atomic no-replace file publication.
        except FileExistsError:
            require(file_hash(path) == sha(payload), f'concurrent write-once artifact differs: {path}')
    finally:
        temporary.unlink(missing_ok=True)


def publish_directory(source: Path, target: Path) -> None:
    """Rename ``source`` to ``target`` atomically, failing instead of replacing an existing target (macOS and Linux only)."""
    if sys.platform == 'darwin':
        libc = ctypes.CDLL(None, use_errno=True)
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        status = rename(os.fsencode(source), os.fsencode(target), 0x4)
    elif sys.platform.startswith('linux'):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, 'renameat2', None)
        require(rename is not None, 'atomic no-replace directory rename unavailable')
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
                           ctypes.c_uint]
        rename.restype = ctypes.c_int
        status = rename(-100, os.fsencode(source), -100, os.fsencode(target), 1)
    else:
        raise ValueError('this helper targets macOS or Linux')
    if status:
        code = ctypes.get_errno()
        if code in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FileExistsError(target)
        raise OSError(code, os.strerror(code), str(target))


def array_bytes(values: np.ndarray) -> bytes:
    """Serialise an array as little-endian float64 ``.npy`` bytes, without pickling, for reproducible hashing."""
    buffer = io.BytesIO()
    np.lib.format.write_array(buffer, np.asarray(values, dtype='<f8'), version=(2, 0),
                              allow_pickle=False)
    return buffer.getvalue()


def matrix_audit(values: np.ndarray, names: list[str]) -> dict[str, Any]:
    """Explain why a synthetic design matrix is rank-deficient.

    Reports the rank, the columns that are identically zero, pairs of identical
    non-zero clinical columns, and the smallest singular values. It also says
    whether removing the zero columns restores full rank.
    """
    singular = np.linalg.svd(values, compute_uv=False)
    rank = int(np.linalg.matrix_rank(values))
    zero = np.flatnonzero(np.max(np.abs(values), axis=0) <= 1e-12)
    nonzero = np.setdiff1d(np.arange(values.shape[1]), zero)
    identical = []
    clinical = np.asarray([i for i in nonzero if not names[i].startswith('gene:')], dtype=int)
    for i in clinical:
        for j in clinical[clinical > i]:
            if np.array_equal(values[:, i], values[:, j]):
                identical.append([names[i], names[j]])
    reduced_rank = int(np.linalg.matrix_rank(values[:, nonzero])) if len(nonzero) else 0
    return {'shape': list(values.shape), 'rank': rank, 'p': values.shape[1],
            'zero_columns': [names[i] for i in zero], 'nonzero_columns': len(nonzero),
            'rank_after_zero_columns_removed': reduced_rank,
            'identical_nonzero_column_pairs': identical,
            'smallest_singular_values': singular[-5:].tolist(),
            'default_rank_tolerance': float(singular[0] * max(values.shape) * np.finfo(values.dtype).eps),
            'full_column_rank': rank == values.shape[1],
            'all_rank_loss_explained_by_zero_columns': reduced_rank == len(nonzero)}


class Audit:
    """Bind a source run and publish separate deterministic failure evidence."""

    def __init__(self, production: Path, run: Path, matched: Path, output: Path) -> None:
        """Verify fitted inputs/runtime before any reconstruction or output."""
        self.production, self.run = production.resolve(strict=True), run.resolve(strict=True)
        self.matched = matched.resolve(strict=True)
        self.output = output.resolve(strict=False)
        if self.output.exists():
            require(self.output.is_dir() and not any(p.is_symlink() for p in self.output.rglob('*')),
                    'existing audit output must be a regular tree without links')
        require(self.production.is_dir() and self.run.is_dir(), 'code and run must be directories')
        for root in (self.production, self.run):
            require(self.output != root and root not in self.output.parents
                    and self.output not in root.parents, 'audit output overlaps production code/results')
            require(not any(p.exists() and p.samefile(root) for p in self.output.parents),
                    'audit output overlaps production code/results by directory identity')
        for name, module in list(sys.modules.items()):
            if name == 'src' or name.startswith('src.'):
                source = getattr(module, '__file__', None)
                require(source is not None and self.production in Path(source).resolve().parents,
                        'foreign src module already imported; run helper in a fresh process')
        sys.path.insert(0, str(self.production))
        import src.pipelines.extensions.preprocessing as prior_module
        from src.data.cohorts import load_analysis_dataset
        from src.data.fold_preprocessing import _as_category
        from src.data.survival_folds import repeated_survival_folds
        from src.pipelines.confirmatory.options import deterministic_seed
        from src.pipelines.extensions.preprocessing import ExtensionPreprocessor
        from src.pipelines.robustness.conditions import apply_administrative_censoring
        from src.utils.io import read_mapping

        self.load_clinical, self.categories = load_analysis_dataset, _as_category
        self.folds = repeated_survival_folds
        self.seed, self.processor = deterministic_seed, ExtensionPreprocessor
        self.prior_module = prior_module
        self.censor, self.read_mapping = apply_administrative_censoring, read_mapping
        self.manifest, manifest_sha = read_json(self.run / 'manifest.json')
        require(canonical_hash({k: v for k, v in self.manifest.items()
                                if k != 'manifest_content_sha256'})
                == self.manifest['manifest_content_sha256'], 'source manifest canonical hash differs')
        commit = self.manifest['code']['git_commit']
        # git-archive restores have no .git. All fitted input files are verified
        # below in either case, which preserves portable content comparisons.
        if (self.production / '.git').exists():
            current = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.production,
                                              text=True).strip()
            require(current == commit, 'source code is not the fitted commit')
        for name, expected in self.manifest['input_sha256'].items():
            path = Path(name)
            require(not path.is_absolute() and '..' not in path.parts, 'unsafe production input path')
            require(file_hash(self.production / path) == expected, f'fitted source input changed: {name}')
        require(file_hash(self.matched) == self.manifest['matched_sha256'], 'matched source changed')
        dependencies = self.manifest['environment']['dependencies']
        require(platform.python_version() == self.manifest['environment']['python'],
                'audit interpreter differs from source runtime')
        for package, actual in (('numpy', np.__version__), ('pandas', pd.__version__)):
            require(dependencies[package] == actual, f'audit {package} differs from source runtime')
        self.config = self.read_mapping(self.production / 'config/extensions.yaml')
        self.specs = self.read_mapping(self.production / 'config/datasets.yaml')
        self.plans = {row['cell_id']: row for row in self.manifest['plan']}
        self.datasets: dict[str, tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]] = {}
        self.bindings = {'source_manifest_sha256': manifest_sha,
                         'source_manifest_content_sha256': self.manifest['manifest_content_sha256'],
                         'source_git_commit': commit, 'source_freeze_content_sha256': self.manifest['freeze_sha256'],
                         'matched_sha256': self.manifest['matched_sha256'],
                         'audit_helper_sha256': file_hash(Path(__file__).resolve()),
                         'runtime': {'python': platform.python_version(), 'numpy': np.__version__, 'pandas': pd.__version__,
                                     'numeric_threads': 1}}

    def dataset(self, name: str) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
        """Read and cache only the cohort required by a failed source cell."""
        if name not in self.datasets:
            if name == 'metabric_matched':
                raw = pd.read_parquet(self.matched)
                data = raw, raw.duration.to_numpy(float), raw.event.to_numpy(int), raw.patient_id.astype(str).to_numpy()
            else:
                require(name in ('gbsg2', 'whas500', 'metabric'), 'unexpected rank-failed dataset')
                data = self.load_clinical(self.production, name, self.specs[name])
            self.datasets[name] = data
        return self.datasets[name]

    def draw(self, training: pd.DataFrame, ids: np.ndarray, processor: Any,
             time: np.ndarray, event: np.ndarray, seed: int, name: str,
             payloads: dict[str, bytes]) -> dict[str, Any]:
        """Capture one reached draw from the unchanged original generator."""
        # Execute the actual sealed function. Local interception captures its
        # source frame and exact constructor arguments, then calls the unchanged
        # original constructor and preserves its error. No source file, worker
        # process, optimizer, sampler, or scientific model is changed.
        captured: dict[str, Any] = {}
        original_constructor = self.prior_module.CatalyticData
        original_transform = processor.transform
        had_transform = 'transform' in processor.__dict__
        saved_transform = processor.__dict__.get('transform')

        def capture_transform(frame: pd.DataFrame) -> pd.DataFrame:
            """Record the synthetic covariate frame before passing it to the original preprocessing transform."""
            captured['synthetic'] = frame.copy()
            return original_transform(frame)

        def capture_constructor(design: np.ndarray, prior_time: np.ndarray, hazard: float) -> Any:
            """Record the synthetic design, times and hazard before passing them to the original constructor."""
            captured.update(design=design.copy(), time=prior_time.copy(), hazard=float(hazard))
            return original_constructor(design, prior_time, hazard)

        self.prior_module.CatalyticData = capture_constructor
        processor.transform = capture_transform
        source_metadata = None
        error = None
        try:
            _, source_metadata = self.prior_module.generate_catalytic_data(
                training, processor, time, event, seed)
        except ValueError as exc:
            error = str(exc)
        finally:
            self.prior_module.CatalyticData = original_constructor
            if had_transform:
                processor.transform = saved_transform
            else:
                del processor.__dict__['transform']
        require({'synthetic', 'design', 'time', 'hazard'} <= set(captured),
                'original generator did not reach the captured constructor')
        synthetic, design, prior_time, hazard = (captured[k] for k in ('synthetic', 'design', 'time', 'hazard'))
        count = len(prior_time)
        scale = float(np.median(time[event == 1]))
        sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
        synthetic_hash = canonical_hash({'X': design.tolist(), 'time': prior_time.tolist()})
        if source_metadata is not None:
            require(source_metadata == {'seed': seed, 'M': count, 'p': len(processor.feature_names),
                                        'time_scale': scale, 'hazard_scaled': hazard,
                                        'source_variables': sources, 'synthetic_sha256': synthetic_hash,
                                        'purpose': 'synthetic prior data; no real or evaluation observations'},
                    'successful original-generator metadata differs from captured arrays')
        check = matrix_audit(design, processor.feature_names)
        check['constructor_error'] = error
        prevalence = {}
        for column in processor.clinical.categorical:
            original, sampled = self.categories(training[column]), self.categories(synthetic[column])
            prevalence[column] = []
            for level in processor.clinical.category_levels[column]:
                n = int((original == level).sum())
                prevalence[column].append({'level': level, 'training_count': n,
                                           'sampled_count': int((sampled == level).sum()),
                                           'retained_encoded_column': f'{column}={level}' in processor.feature_names,
                                           'omission_probability_iid_marginal_draw': float((1 - n / len(training)) ** count)})
        arrays = {}
        for filename, values in (('X.npy', design), ('time.npy', prior_time)):
            relative = f'draws/{name}/{filename}'
            data = array_bytes(values)
            payloads[relative] = data
            arrays[filename] = {'path': relative, 'bytes': len(data), 'sha256': sha(data),
                                'shape': list(values.shape), 'dtype': '<f8', 'format': 'NPY v2.0; no pickle'}
        return {'stage': name, 'seed': seed, 'M': count, 'p': len(processor.feature_names),
                'n_training': len(training), 'training_membership_sha256': canonical_hash(ids.tolist()),
                'training_time_event_sha256': canonical_hash({'time': time.tolist(), 'event': event.tolist()}),
                'time_scale': scale, 'hazard_scaled': hazard, 'source_variables': sources,
                'synthetic_sha256': synthetic_hash,
                'preprocessing': processor.metadata(), 'source_category_prevalence': prevalence,
                'matrix': check, 'training_matrix': matrix_audit(processor.transform(training).to_numpy(float),
                                                                processor.feature_names),
                'arrays': arrays,
                'source_generator_called': True, 'unchanged_original_constructor_called': True,
                'successful_original_generator_metadata_verified': source_metadata is not None,
                'execution_relationship': 'post-hoc reconstruction of a generator draw reached by the source job'}

    def reconstruct(self, cell: dict[str, Any], cell_sha: str) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Reproduce the first failed draw and any preceding reached inner draws."""
        require(cell.get('status') == 'failed' and cell.get('message') == RANK_MESSAGE
                and cell.get('error_type') == 'ValueError', 'source cell is not a ValueError rank failure')
        require(not any(name in cell for name in ('metrics', 'predictions', 'fit_attempts')),
                'rank-failed source cell contains outer fit attempts or evaluated outcomes')
        require('generate_catalytic_data' in cell.get('traceback', '')
                and '__post_init__' in cell.get('traceback', ''),
                'source traceback does not show pre-fit generator validation')
        raw, times, events, ids = self.dataset(cell['dataset'])
        lookup = {str(value): index for index, value in enumerate(ids)}
        tr = np.asarray([lookup[str(value)] for value in cell['train_subject_ids']], dtype=int)
        va = np.asarray([lookup[str(value)] for value in cell['validation_subject_ids']], dtype=int)
        plan = self.plans[cell['cell_id']]
        require(canonical_hash(ids[tr].tolist()) == cell['training_membership_sha256'] == plan['train_sha256']
                and canonical_hash(ids[va].tolist()) == plan['validation_sha256'], 'source job membership differs')
        require(cell['seed'] == self.seed(self.config['base_seed'], 'extensions', cell['cell_id']),
                'source cell seed differs from frozen rule')
        key = 'metabric' if cell['dataset'] == 'metabric_matched' else cell['dataset']
        spec = self.specs[key]['primary_features']
        training = raw.iloc[tr]
        tt, ee = self.censor(times[tr], events[tr], cell['censoring_cutoff'])
        processor = self.processor(spec, cell['gene_budget']).fit(training)
        require(processor.metadata() == cell['preprocessing'], 'reconstructed outer preprocessing differs from saved state')
        require(len(processor.feature_names) == cell['p'], 'reconstructed p differs from saved p')
        reported_stage = 'inner' if 'in select_parameters' in cell['traceback'] else 'outer'
        payloads: dict[str, bytes] = {}
        draws = []
        failed = None
        if cell['model_key'] == 'catalytic_wme':
            inner_seed = self.seed(cell['seed'], 'inner_cv')
            for fold in self.folds(tt, ee, n_splits=3, n_repeats=1, base_seed=inner_seed, max_time_bins=4):
                idx = fold.train_indices
                inner_processor = self.processor(spec, cell['gene_budget']).fit(training.iloc[idx])
                draw = self.draw(training.iloc[idx], ids[tr][idx], inner_processor, tt[idx], ee[idx],
                                 self.seed(inner_seed, 'inner_prior', fold.fold), f'inner_{fold.fold:02}', payloads)
                draws.append(draw)
                if not draw['matrix']['full_column_rank']:
                    failed = draw
                    break  # Later draws and the outer draw were never reached.
        if failed is None:
            require(reported_stage == 'outer', 'reported inner failure did not reproduce')
            failed = self.draw(training, ids[tr], processor, tt, ee,
                               self.seed(cell['seed'], 'outer_prior'), 'outer', payloads)
            draws.append(failed)
        else:
            require(reported_stage == 'inner', 'reconstruction failed earlier than source job')
        require(failed['matrix']['constructor_error'] == RANK_MESSAGE,
                'actual first failing synthetic draw did not reproduce')
        matrix = failed['matrix']
        result = {'schema_version': 1, 'evidence_status': CLASSIFICATION,
                  'programme_completion': 'not_assessed', 'scientific_model_fits_performed': False,
                  'patient_level_records_written': False,
                  'bindings': {**self.bindings, 'failed_cell_sha256': cell_sha,
                               'failed_cell_content_sha256': cell['cell_content_sha256']},
                  'cell_id': cell['cell_id'], 'dataset': cell['dataset'], 'setting': cell['setting'],
                  'condition': cell['condition'], 'model_key': cell['model_key'], 'cell_seed': cell['seed'],
                  'outer_training_membership_sha256': cell['training_membership_sha256'],
                  'outer_preprocessing_state_sha256': processor.metadata()['state_sha256'],
                  'saved_outer_preprocessing_verified': True, 'first_failing_draw': failed['stage'],
                  'source_failure_error_type': 'ValueError', 'source_outer_fit_attempts_absent': True,
                  'source_metrics_and_predictions_absent': True,
                  'failure_cause': ('retained indicator levels omitted by the frozen iid marginal draw'
                                    if matrix['zero_columns'] and matrix['all_rank_loss_explained_by_zero_columns']
                                    else 'rank loss requires inspection beyond zero columns'),
                  'draws': draws,
                  'frozen_handling': 'source implementation rejects rank-deficient draws; no frozen recovery rule',
                  'recording_boundary': 'source generator raised before returning metadata; this sidecar reconstructs it without altering source cells'}
        result['content_sha256'] = canonical_hash(result)
        payloads['case.json'] = json_bytes(result)
        return result, payloads

    def publish_case(self, identity: str, payloads: dict[str, bytes]) -> tuple[Path, bool]:
        """Publish a new case atomically or reverify its write-once bytes."""
        require(re.fullmatch(r'[A-Za-z0-9_.-]+', identity) is not None, 'unsafe cell identifier')
        parent = self.output / 'cases'
        parent.mkdir(parents=True, exist_ok=True)
        require(not parent.is_symlink(), 'linked cases directory refused')
        target = parent / identity

        def verify() -> None:
            """Check that an already-published case holds exactly the expected files, each with identical bytes."""
            require(target.is_dir() and not target.is_symlink(), 'existing case is not a regular audit tree')
            actual = set()
            for p in target.rglob('*'):
                require(not p.is_symlink(), 'linked audit case artifact refused')
                if p.is_file():
                    actual.add(p.relative_to(target).as_posix())
            require(actual == set(payloads), f'existing case inventory differs: {identity}')
            for name, expected in payloads.items():
                require(file_hash(target / name) == sha(expected), f'write-once reconstructed artifact differs: {identity}/{name}')

        if target.exists() or target.is_symlink():
            verify()
            return target, False
        stage = Path(tempfile.mkdtemp(prefix='.rank-case-', dir=parent))
        try:
            for name, payload in payloads.items():
                write_once(stage / name, payload)
            try:
                publish_directory(stage, target)
            except FileExistsError:
                verify()
            else:
                verify()
        finally:
            shutil.rmtree(stage, ignore_errors=True)
        return target, True

    def execute(self) -> dict[str, Any]:
        """Audit currently stored rank failures and publish a portable snapshot."""
        available = sorted((self.run / 'cells').glob('*.json'))
        cases = []
        new_count = 0
        for path in available:
            cell, digest = read_json(path)
            if cell.get('status') != 'failed' or cell.get('message') != RANK_MESSAGE:
                continue
            require(canonical_hash({k: v for k, v in cell.items() if k != 'cell_content_sha256'})
                    == cell['cell_content_sha256'], 'failed source cell canonical hash differs')
            require(cell['cell_id'] in self.plans and path.stem == cell['cell_id'], 'failed cell is not in source plan')
            record, payloads = self.reconstruct(cell, digest)
            require(file_hash(path) == digest, 'failed source cell changed during reconstruction')
            destination, created = self.publish_case(cell['cell_id'], payloads)
            new_count += created
            failed = next(draw for draw in record['draws'] if draw['stage'] == record['first_failing_draw'])
            cases.append({'cell_id': cell['cell_id'], 'source_cell_sha256': digest,
                          'sidecar': (destination / 'case.json').relative_to(self.output).as_posix(),
                          'sidecar_sha256': sha(payloads['case.json']),
                          'first_failing_draw': record['first_failing_draw'],
                          'rank': failed['matrix']['rank'], 'p': failed['p'],
                          'zero_columns': failed['matrix']['zero_columns'],
                          'failure_cause': record['failure_cause']})
        snapshot = {'schema_version': 1, 'evidence_status': CLASSIFICATION,
                    'programme_completion': 'not_assessed', 'bindings': self.bindings,
                    'available_source_cells_scanned': len(available), 'planned_source_cells': self.manifest['planned_fits'],
                    'source_grid_counts': {'planned': self.manifest['planned_fits'], 'stored': len(available)},
                    'rank_failed_cells_audited': len(cases), 'cases': cases,
                    'scientific_model_fits_performed': False, 'patient_level_records_written': False,
                    'scope': 'actual first rank-failing draws plus any preceding reached WME inner draws; no unreached draws'}
        snapshot['content_sha256'] = canonical_hash(snapshot)
        relative = f'snapshots/failure_provenance_{snapshot["content_sha256"]}.json'
        write_once(self.output / relative, json_bytes(snapshot))
        require(file_hash(self.run / 'manifest.json') == self.bindings['source_manifest_sha256'],
                'source manifest changed during audit')
        require(file_hash(Path(__file__).resolve()) == self.bindings['audit_helper_sha256'],
                'audit helper changed during execution')
        return {'evidence_status': CLASSIFICATION, 'programme_completion': 'not_assessed',
                'snapshot': str(self.output / relative), 'snapshot_sha256': sha(json_bytes(snapshot)),
                'snapshot_content_sha256': snapshot['content_sha256'],
                'rank_failed_cells_audited': len(cases), 'new_case_sidecars': new_count,
                'reverified_existing_case_sidecars': len(cases) - new_count}


def write_failure_provenance(production: Path, run: Path, matched: Path,
                             output: Path) -> dict[str, Any]:
    """Reconstruct and publish resumable write-once failure audit sidecars.

    Call in a fresh process with the source lock's Python runtime; the output is
    a directory outside production code/results, and can contain prior sidecars
    from this exact helper. Returned paths are convenience output only. All JSON
    comparison fields and array paths inside the evidence are portable.
    """
    return Audit(production, run, matched, output).execute()


def main() -> None:
    """Command-line entry point: reconstruct the rank-failure provenance and print the JSON result."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('production-code', 'run', 'matched', 'output'):
        parser.add_argument(f'--{name}', type=Path, required=True)
    args = parser.parse_args()
    result = write_failure_provenance(args.production_code, args.run, args.matched, args.output)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
