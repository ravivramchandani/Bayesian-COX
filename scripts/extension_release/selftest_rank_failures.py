#!/usr/bin/env python3
"""Focused integrity tests; optionally verify real reconstructed sidecars."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import audit_rank_failures as audit

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--sidecars', type=Path)
args, unittest_args = parser.parse_known_args()


class FocusedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix='rank-audit-selftest-')
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def source_cell(self) -> dict:
        return {'status': 'failed', 'message': audit.RANK_MESSAGE, 'error_type': 'ValueError',
                'traceback': 'generate_catalytic_data -> __post_init__'}

    def test_unicode_canonical_hash_uses_utf8(self) -> None:
        expected = hashlib.sha256('{"label":"Δ"}'.encode()).hexdigest()
        self.assertEqual(audit.canonical_hash({'label': 'Δ'}), expected)

    def test_npy_is_deterministic_and_round_trips_without_pickle(self) -> None:
        values = audit.np.asarray([[1, 2], [3, 4]], dtype=float)
        first = audit.array_bytes(values)
        self.assertEqual(first, audit.array_bytes(values))
        restored = audit.np.load(io.BytesIO(first), allow_pickle=False)
        audit.np.testing.assert_array_equal(restored, values)

    def test_matrix_audit_distinguishes_zero_and_duplicate_directions(self) -> None:
        independent = audit.np.asarray([[1, 0, 0], [0, 1, 0], [1, 1, 0]], dtype=float)
        record = audit.matrix_audit(independent, ['one', 'two', 'empty'])
        self.assertEqual(record['zero_columns'], ['empty'])
        self.assertTrue(record['all_rank_loss_explained_by_zero_columns'])
        dependent = audit.np.asarray([[1, 1], [0, 0], [2, 2]], dtype=float)
        record = audit.matrix_audit(dependent, ['one', 'duplicate'])
        self.assertFalse(record['all_rank_loss_explained_by_zero_columns'])
        self.assertEqual(record['identical_nonzero_column_pairs'], [['one', 'duplicate']])

    def test_write_once_refuses_changed_payload(self) -> None:
        path = self.root / 'receipt.json'
        audit.write_once(path, b'original\n')
        audit.write_once(path, b'original\n')
        with self.assertRaisesRegex(ValueError, 'existing write-once artifact differs'):
            audit.write_once(path, b'changed\n')
        self.assertEqual(path.read_bytes(), b'original\n')

    def test_write_once_refuses_symlink(self) -> None:
        path = self.root / 'original'
        path.write_bytes(b'original\n')
        alias = self.root / 'alias'
        alias.symlink_to(path.name)
        with self.assertRaisesRegex(ValueError, 'linked audit input'):
            audit.write_once(alias, b'original\n')

    def test_wrong_error_type_cannot_claim_pre_fit_rank_failure(self) -> None:
        instance = object.__new__(audit.Audit)
        cell = self.source_cell()
        cell['error_type'] = 'RuntimeError'
        with self.assertRaisesRegex(ValueError, 'not a ValueError rank failure'):
            instance.reconstruct(cell, '0' * 64)

    def test_fit_or_prediction_fields_cannot_claim_pre_fit_failure(self) -> None:
        instance = object.__new__(audit.Audit)
        for field in ['metrics', 'predictions', 'fit_attempts']:
            with self.subTest(field=field):
                cell = {**self.source_cell(), field: []}
                with self.assertRaisesRegex(ValueError, 'contains outer fit attempts or evaluated outcomes'):
                    instance.reconstruct(cell, '0' * 64)

    def test_missing_constructor_traceback_cannot_claim_pre_fit_failure(self) -> None:
        instance = object.__new__(audit.Audit)
        cell = self.source_cell()
        cell['traceback'] = 'an unrelated error'
        with self.assertRaisesRegex(ValueError, 'does not show pre-fit generator validation'):
            instance.reconstruct(cell, '0' * 64)

    def test_cached_case_is_rehashed_and_corruption_rejected(self) -> None:
        instance = object.__new__(audit.Audit)
        instance.output = self.root
        payloads = {'case.json': b'{"artificial": true}\n', 'draws/outer/X.npy': b'artificial array\n'}
        target, created = instance.publish_case('artificial_case', payloads)
        self.assertTrue(created)
        _, created = instance.publish_case('artificial_case', payloads)
        self.assertFalse(created)
        (target / 'draws/outer/X.npy').write_bytes(b'changed array\n')
        with self.assertRaisesRegex(ValueError, 'write-once reconstructed artifact differs'):
            instance.publish_case('artificial_case', payloads)

    def test_existing_extra_case_artifact_rejected(self) -> None:
        instance = object.__new__(audit.Audit)
        instance.output = self.root
        payloads = {'case.json': b'{}\n'}
        target, _ = instance.publish_case('artificial_case', payloads)
        (target / 'extra.txt').write_text('unexpected\n')
        with self.assertRaisesRegex(ValueError, 'existing case inventory differs'):
            instance.publish_case('artificial_case', payloads)

    def test_existing_publish_target_is_not_overwritten(self) -> None:
        stage, target = self.root / 'stage', self.root / 'target'
        stage.mkdir()
        target.mkdir()
        (target / 'preserve').write_bytes(b'preserve\n')
        with self.assertRaises(FileExistsError):
            audit.publish_directory(stage, target)
        self.assertEqual((target / 'preserve').read_bytes(), b'preserve\n')

    @unittest.skipIf(args.sidecars is None, 'pass --sidecars to check reconstructed artifacts')
    def test_real_sidecar_content_and_exact_array_inventory(self) -> None:
        root = args.sidecars.resolve(strict=True)
        cases = sorted((root / 'cases').iterdir())
        self.assertGreater(len(cases), 0)
        for folder in cases:
            record = json.loads((folder / 'case.json').read_text())
            self.assertEqual(record['evidence_status'], audit.CLASSIFICATION)
            self.assertEqual(record['programme_completion'], 'not_assessed')
            self.assertEqual(record['source_failure_error_type'], 'ValueError')
            self.assertTrue(record['source_outer_fit_attempts_absent'])
            self.assertTrue(record['source_metrics_and_predictions_absent'])
            self.assertEqual(record['content_sha256'], audit.canonical_hash({k: v for k, v in record.items()
                                                                            if k != 'content_sha256'}))
            expected = {'case.json'}
            self.assertEqual(record['first_failing_draw'], record['draws'][-1]['stage'])
            for index, draw in enumerate(record['draws']):
                self.assertTrue(draw['source_generator_called'])
                self.assertTrue(draw['unchanged_original_constructor_called'])
                self.assertEqual(draw['preprocessing']['state_sha256'],
                                 audit.canonical_hash({k: v for k, v in draw['preprocessing'].items()
                                                       if k != 'state_sha256'}))
                for array in draw['arrays'].values():
                    path = Path(array['path'])
                    self.assertFalse(path.is_absolute())
                    self.assertNotIn('..', path.parts)
                    data = (folder / path).read_bytes()
                    expected.add(path.as_posix())
                    self.assertEqual(array['bytes'], len(data))
                    self.assertEqual(array['sha256'], audit.sha(data))
                    values = audit.np.load(io.BytesIO(data), allow_pickle=False)
                    self.assertEqual(array['shape'], list(values.shape))
                    self.assertTrue(audit.np.isfinite(values).all())
                design = audit.np.load(folder / draw['arrays']['X.npy']['path'], allow_pickle=False)
                time = audit.np.load(folder / draw['arrays']['time.npy']['path'], allow_pickle=False)
                self.assertEqual(draw['synthetic_sha256'], audit.canonical_hash({'X': design.tolist(), 'time': time.tolist()}))
                matrix = audit.matrix_audit(design, draw['preprocessing']['feature_names'])
                self.assertEqual(matrix['rank'], draw['matrix']['rank'])
                self.assertEqual(matrix['zero_columns'], draw['matrix']['zero_columns'])
                if index + 1 < len(record['draws']):
                    self.assertTrue(matrix['full_column_rank'])
                    self.assertTrue(draw['successful_original_generator_metadata_verified'])
                else:
                    self.assertFalse(matrix['full_column_rank'])
            actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
            self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main(argv=['selftest_rank_failures.py', *unittest_args], verbosity=2)
