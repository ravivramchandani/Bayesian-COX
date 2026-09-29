"""Portable source-only imports for separately sealed fictional dispatch guards.

The corrected v3 source carrier and every retained fixture method are byte pinned.
No production approval, controller or scientific operation belongs to this helper.
"""

from __future__ import annotations

import ast
import atexit
import builtins
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

PREPARATION_SHA = "65db400992816a3628c0177ee4e90b777be4c8aa6f139add0a7799b434ef176a"
SOURCE_SHA = {'capture_guarded_dispatch.py': 'f82a7b8d2c65e829a7178c8fb230751bef193356e8589c22512ac229de944611',
 'guard_fit_dispatch.py': '368141f522b8d2d9b4d8829a0c1102d326bd7aafc6b063ee574932f02c33c116',
 'verify_guarded_dispatch_proof.py': '7b19d4c7efa945d22e03cc779e1a1e64a06425f59a7d6b7d862097708ec501a9'}
TEST_SHA = {'test_guarded_dispatch.py': '1f149bbf44a90580f63de55678ae196480615f16a83d16c542d6dfbc628a521f',
 'test_guarded_dispatch_regressions.py': '0b9e0d56a71613b066baa96e4927567bbdfeb11642ef2905087b2a5f2020633a',
 'test_guarded_dispatch_reuse_consistency.py': '5bdff58f9265b0d01ac2e4b98b57de6c45c48d88c69bfb66c339d0fce3b86ec7'}
TEST_ORDER = ("test_guarded_dispatch.py", "test_guarded_dispatch_regressions.py", "test_guarded_dispatch_reuse_consistency.py")
CARRIER_MEMBERS = 116
BOUND_ARTIFACTS = 115
CARRIER_DIRECTORIES = ("preserved_v2", "preserved_v2/preserved_v1", "preserved_v2/preserved_v1_review", "preserved_v2_review")
ORIGINAL_METHOD_AST = {'test_actual_pinned_stdlib_bootstrap_refuses_fixture_and_restores_aliases': '237c896f9276d562ae4ce2d9582ac8ae162a18d1d9debdfbb433d80b89a8d7e4',
 'test_all_actual_arguments_match_including_optional_reviews_and_limit': 'df6dd865d085779f6de177cf9480b6dfceb66b48ee54309db77331677f0dafe7',
 'test_change_after_owned_launcher_preflight_refuses_controller': 'a2a90e8048080430ca8084e141d4a9a64b63676ade52bdd697610748853b3722',
 'test_changed_resume_bytes_extra_attempt_and_history_gap_block': 'df99e47f136370a04eb10e6fc3ba2e6106111dc3e458776937e974f64c0e3493',
 'test_empty_orphan_attempt_and_claim_directory_refuse_without_cleanup': '31c8b3f13e8acc5f805bd7e7284f3424c06fcb98c4dbd1d24549c7d0243e2ba2',
 'test_exclusive_publication_and_noninteger_or_unavailable_return': '270b7ba550fe77e8578ea7d3bade3e754b1b17182d9696d17ba5fbe060c9e922',
 'test_future_dated_named_review_refused': '1575f33934195d11cfc500a1c65895856422e54447fc5f60ceb1dcb9618f2516',
 'test_genuine_two_mocked_captures_introduction_before_controller': '38471eb53096986adcf34b2a35939f2307a0eddb1016fe0d1e793951fa4ed43e',
 'test_guard_preparation_reproduction_ancestry_overlap_before_any_write': '7415c3b8450e90135f323ac4e01961755a45032606b2233af143018c2fcfca66',
 'test_location_authority_empty_dirs_extra_bytes_and_aliases_refused': '9315fb5c60c456c36d215bd0fa2205a266b8547ab91b81f29f334345eeccfba0',
 'test_missing_or_false_pilot_binding_refuses_remaining': 'b0a5188b9bf50da9d7a71f94e52d3afcce933ed8e2021b761a06327d9bce920f',
 'test_named_review_and_pre_freeze_guard_binding_required': '96e3ae055a4ec68203178422719e64542811a94c22cf04fa0591d530e7f61fa4',
 'test_narrow_old_helper_cannot_hide_bad_freeze_definition_witness_or_flags': 'c04968d51f6258b679ff09cc32a905cfa3263d09264896c0c8190747aa59570a',
 'test_nonzero_controller_retains_raw_and_failed_bytes_without_success': 'ab4dfd46d332b25032808178d3855cbbee088c4186003b30cf2c9bc574c3a84e',
 'test_original_helpers_accept_exact_no_fit_account_and_existing_pass': 'aa95868ef90f09b7535eed10575a1aa73341fadf0b4156ae0dabab012dc523a2',
 'test_partial_parent_capture_is_preserved_and_not_promoted': 'd6113800210c67dc9cafde1546d1c9884776947afb8250a37457ae80fe5cb8a7',
 'test_preparation_rejects_unlisted_file_and_empty_directory': '4b47c033f5a0f9b15a3559a7f8f4f8ba0d695151eb02c860c9313b6a621b72c4',
 'test_prior_fit_rejected_even_latest_pass_account': '7ea2178eecf5e909faf44692cd646c015c5da79288912fc1ab2e00c8a91c711d',
 'test_receiving_identity_missing_relocation_and_wrong_role_refused': '88687410753c52d8c5d33989fcd10f35c8e28770ecf342dadb17775c078c1be2',
 'test_remaining_uses_exact_original_pilot_predicate_and_resume_history': 'f7cd2d413eb8bb97ef341e9d33e922e877547478fd81aa310902d4e069811152',
 'test_source_and_restored_readonly_semantics_and_external_output': '8928f3ed87c19d418b84be20f3dec2c49b094816f723d289c70e946d49e63ef7',
 'test_source_symlink_traversal_occupied_alias_and_numeric_env_refused': '4745e9a43231f30854115b4f593ddad17f7a1a1bd2dce0d5930ee48e0edfb80d',
 'test_synthetic_request_cannot_authorize_production': '84fbf4cd3ed9fd86dc34554c58c43bb33e37a557940b5a9f63445b35d95099f7'}
REGRESSION_METHOD_AST = {'test_account_pass_counts_flags_hashes_and_subset_chain_refused': 'ba9cf7fc279bbc2d4fca64f8b886efc0cb09f02a0cc1717980a931dd658b5c4d',
 'test_actual_six_corrected_fit_fields_and_unknown_score_field_refused': '4d9574e41a252fd9d9cc924afc666902ce02d3aa959b28347421ade529de2ae2',
 'test_all_legitimate_pending_rows_without_cells_are_kept': 'bde85b69b2c556accaeaf029bae46206bfb14fc76a9747fadd99de1bab5c7411',
 'test_bound_file_siblings_allowed_and_only_corrected_selection_role_exempt': '9d0fe163c326744572f484190348425e981c2d70692968ae31234281aff9c35f',
 'test_duplicate_foreign_reordered_or_extra_pending_fields_refused': '42b446089a44e8886c6e4703a8c24668e95b0ab333510d73dfc0cd306025d2f8',
 'test_every_declared_immutable_role_and_request_is_protected_both_directions': '3762fb5be64aafb3bf033442f97d84c4a42d006a0d3883cefb13da8be4485de1',
 'test_foreign_numeric_false_flag_row_and_arbitrary_status_refused': '0f732af8caa283a0dc2ffe150c5ca89098e14a9ac75661ac0a253cedd1778b13',
 'test_legitimate_original_success_and_negative_reuse_kept': '454880b1849d0b11820ca3f3efe01ee8ca6b3d189d6d05f83cebe239ce64d0ef',
 'test_partial_account_history_pending_then_terminal_then_more_cells_kept': '6d290ac0087958e41c3c35bc7ab11b6e241118cc0ecab523a70eddb12d4fba17',
 'test_reuse_reference_and_terminal_decision_status_must_match': '52c36e36349f85a8fe7d6bd0e8bde21efc36366aa39cc331f1eda495386a409e',
 'test_selection_only_original_reproduction_descendant_refused_before_first_write': '2fbcb1bb0bd2136cecaea4d4e83dfe28edb543b35212f097b7eee64b1840353c'}
CONSISTENCY_METHOD_AST = {'test_original_negative_reuse_statuses_remain_valid': '9d6e698b1fabcb05f945a2fb05c50d2d5c0df9f92727e570b58ce38dba70d394',
 'test_reused_changed_roles_impossible_and_refused': '3c9007a2a242b78688d943b7f910f4d5a65bad26cbe97f2fbe57e8bc82949417',
 'test_reused_generator_failure_impossible_and_refused': 'b0c71b23a432566af737279488792869278f9019ffa4ae02c6a96c390b95164a',
 'test_reused_missing_roles_impossible_and_refused': 'e0276e55eeb8165fd4925fec9a1a362f57f3f900d3a4cdcb1669669617063176',
 'test_reused_nonnull_tuning_marker_impossible_and_refused': 'cbba4eba74441291bd321ae5b157fccb3534b003be59b47bba7f7abf08edbf08',
 'test_terminal_failures_keep_legitimate_missing_and_changed_roles': '8284c7969c85d40d4379739bc97cf2397d7eafbf1f3e3eb3cd5d287ec4cf4e88',
 'test_terminal_nonnull_tuning_marker_impossible_and_refused': '813e9f3069e2dc1a29e7db65babee4f6da20725ace4d172df9962e44f66cd23a'}
FIT_PINS = {
    "fit_common.py": "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11",
    "fit_child.py": "8ec459f949d7edb18bb587b42eab5baa823fa606075b086c8a5b2475256b2935",
    "fit_controller.py": "1fdeecc9d437bae930414bc84094da01f21140e6db86e09193cf47a395f1a038",
}
REPRODUCTION_PINS = {
    "reproduction_core.py": "fa43d4c75f231a59f12adb73b312627744b6c40dd0a97c002016ed4cba597cb5",
    "run_reproduction.py": "86eed8bd3af2f5ddab9b1bf354e7251518cfb64932da778d05d63a937209829c",
    "terminal_replay_child.py": "830e866d38eb65f9742cb9e7e48212f532ee1d1bfd9eeb7791ca89dbe3dacc61",
}
ALIASES = frozenset({
    "fit_common", "_reproduction_bound_common", "_guard_old_reproduction",
    "_guard_old_controller", "_guard_dispatch_runtime", "_fictional_guard_core",
    "_fictional_guard_capture", "test_guarded_dispatch",
    "test_guarded_dispatch_regressions", "test_guarded_dispatch_reuse_consistency",
})
SCIENCE_PREFIXES = ("src", "numpy", "pandas", "scipy", "arviz", "pymc", "pytensor", "sksurv", "lifelines", "torch", "jax")
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
OWNED_FIXTURE_PREFIXES = ("_fictional_common_", "_fictional_controller_")


class InvalidFixture(ValueError):
    """A fixture cannot borrow unknown source, mutate caller state or run jobs."""


def require(value: Any, message: str) -> None:
    if not value:
        raise InvalidFixture(message)


def safe(path: Path) -> Path:
    require(path.is_absolute() and ".." not in path.parts
            and not any(p.is_symlink() for p in (path, *path.parents)), "absolute unlinked fixture path required")
    return path


def sha(path: Path) -> str:
    safe(path)
    require(path.is_file(), "regular bound member required")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def json_value(raw: bytes | str) -> Any:
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    def nonfinite(value):
        raise InvalidFixture("nonfinite JSON " + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def document(path: Path, expected: str) -> dict[str, Any]:
    require(sha(path) == expected, "document byte binding differs")
    value = json_value(path.read_bytes())
    require(isinstance(value, dict) and value["content_sha256"] == canonical({k: v for k, v in value.items() if k != "content_sha256"}), "document content seal differs")
    require(sha(path) == expected, "document changed while read")
    return value


def method_surface(source: Path) -> dict[str, str]:
    path = source / "test_guarded_dispatch.py"
    require(sha(path) == TEST_SHA[path.name], "original fixture source differs")
    tree = ast.parse(path.read_bytes())
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "GuardTests"]
    require(len(classes) == 1, "original fixture class differs")
    surface = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
               for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    require(surface == ORIGINAL_METHOD_AST and len(surface) == 23, "original23 method definitions differ")
    original = source / "preserved_v2/preserved_v1/test_guarded_dispatch.py"
    require(sha(original) == "a75133f84b795129967583cb29035c1cd6f70364af78a407eff921805f9af0bd", "preserved v1 fixture bytes differ")
    old_class = [node for node in ast.parse(original.read_bytes()).body if isinstance(node, ast.ClassDef) and node.name == "GuardTests"]
    require(len(old_class) == 1, "preserved original fixture class differs")
    old_surface = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
                   for node in old_class[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    require(old_surface == surface, "one of the retained original23 methods was rewritten")
    return surface


def regression_surface(source: Path) -> dict[str, str]:
    path = source / "test_guarded_dispatch_regressions.py"
    require(sha(path) == TEST_SHA[path.name], "regression source differs")
    classes = [node for node in ast.parse(path.read_bytes()).body if isinstance(node, ast.ClassDef) and node.name == "GuardV2Regressions"]
    require(len(classes) == 1, "regression fixture class differs")
    surface = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
               for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    require(surface == REGRESSION_METHOD_AST and len(surface) == 11, "all11 regression methods required")
    return surface


def consistency_surface(source: Path) -> dict[str, str]:
    path = source / "test_guarded_dispatch_reuse_consistency.py"
    require(sha(path) == TEST_SHA[path.name], "consistency source differs")
    classes = [node for node in ast.parse(path.read_bytes()).body if isinstance(node, ast.ClassDef) and node.name == "GuardV3ReuseConsistency"]
    require(len(classes) == 1, "consistency fixture class differs")
    surface = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
               for node in classes[0].body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    require(surface == CONSISTENCY_METHOD_AST and len(surface) == 7, "all7 consistency methods required")
    return surface


def validate_surface(source: Path) -> dict[str, Any]:
    safe(source)
    require(source.is_dir() and len(PREPARATION_SHA) == 64 and SOURCE_SHA and TEST_SHA, "corrected sealed carrier identity required")
    value = document(source / "preparation_receipt.json", PREPARATION_SHA)
    require(value["status"] == "guarded_dispatch_preparation_sealed" and value["test_only"] is False
            and value["actual_controller_or_scientific_dispatch"] is False
            and value["actual_root_reviews_selection_freeze_adoption_or_approvals_created"] is False
            and value["implementation_preparation_version"] == 3 and value["v2_adopted"] is False
            and value["retained_test_methods"] == 34 and value["new_consistency_regression_methods"] == 7
            and value["focused_test_methods"] == 41
            and value["retained34_method_AST_and_source_byte_exact"] is True
            and value["old6_import_source_pins_unchanged"] is True
            and value["new_consistency_method_ASTs"] == CONSISTENCY_METHOD_AST
            and value["retained34_method_surface"] == {
                "test_guarded_dispatch.py": {"binding": {"bytes": 37287, "sha256": TEST_SHA["test_guarded_dispatch.py"]},
                                              "method_ASTs": ORIGINAL_METHOD_AST},
                "test_guarded_dispatch_regressions.py": {"binding": {"bytes": 15012, "sha256": TEST_SHA["test_guarded_dispatch_regressions.py"]},
                                                          "method_ASTs": REGRESSION_METHOD_AST}}
            and value["runtime_source_sha256"] == SOURCE_SHA, "honest prepared source surface differs")
    artifacts = value["artifacts"]
    require(len(artifacts) == BOUND_ARTIFACTS and value["bound_artifact_count"] == BOUND_ARTIFACTS
            and value["archival_member_count_including_receipt"] == CARRIER_MEMBERS, "full source carrier counts differ")
    expected = set(artifacts) | {"preparation_receipt.json"}
    actual, directories = set(), []
    for member in source.rglob("*"):
        require(not member.is_symlink() and (member.is_file() or member.is_dir()), "unsafe carrier node")
        (actual.add(str(member.relative_to(source))) if member.is_file()
         else directories.append(str(member.relative_to(source))))
    require(actual == expected and sorted(directories) == value["artifact_directories"] == list(CARRIER_DIRECTORIES), "complete carrier roster differs")
    for name, binding in artifacts.items():
        relative = Path(name)
        require(name not in {"", "."} and not relative.is_absolute() and ".." not in relative.parts and str(relative) == name, "unsafe carrier artifact")
        member = source / relative
        require(type(binding["bytes"]) is int and binding["bytes"] >= 0
                and sha(member) == binding["sha256"] and member.stat().st_size == binding["bytes"], "source carrier artifact differs")
    for name, pin in {**SOURCE_SHA, **TEST_SHA}.items():
        require(sha(source / name) == pin, "reviewed source or test bytes differ")
    method_surface(source)
    regression_surface(source)
    consistency_surface(source)
    for name in ("test_guarded_dispatch.py", "test_guarded_dispatch_regressions.py"):
        require(sha(source / "preserved_v2" / name) == TEST_SHA[name], "one of the retained34 source files differs from v2")
    require(sha(source / "preparation_receipt.json") == PREPARATION_SHA, "carrier changed before return")
    return value


def configured(test_file: Path) -> tuple[Path, dict[str, Path]]:
    repo = Path(os.environ.get("BAYES_COX_GUARD_TEST_REPOSITORY_ROOT", str(test_file.absolute().parents[1]))).absolute()
    support = repo / "scripts/catalytic_correction"
    source = Path(os.environ.get("BAYES_COX_GUARD_TEST_SOURCE_ROOT", str(support / "guarded_dispatch"))).absolute()
    return source, {"fit": support, "reproduction": support / "reproduction"}


def fixture_parent() -> Path | None:
    value = os.environ.get("BAYES_COX_GUARD_TEST_FIXTURE_ROOT")
    if value is None:
        return None
    path = safe(Path(value).absolute())
    require(path.is_dir(), "existing absolute fixture scratch required")
    return path


def science_names() -> set[str]:
    return {name for name in sys.modules if any(name == prefix or name.startswith(prefix + ".") for prefix in SCIENCE_PREFIXES)}


class FixtureJson:
    """Resolve only the original fixture's exact recorded source-binding text."""

    def __init__(self, raw: str, roots: dict[str, Path]) -> None:
        self.raw, self.roots = raw, roots

    def __getattr__(self, name):
        return getattr(json, name)

    def loads(self, raw, *args, **kwargs):
        value = json.loads(raw, *args, **kwargs)
        if isinstance(raw, str) and raw == self.raw:
            require(value["fit_code"] and value["reproduction_code"], "recorded fixture roots absent")
            value["fit_code"] = str(self.roots["fit"])
            value["reproduction_code"] = str(self.roots["reproduction"])
        return value


class FixtureTempfile:
    """Track only source-fixture tempdirs so failed setUp cannot leak them."""

    def __init__(self, parent: Path, owned: list[Any]) -> None:
        self.parent, self.owned = parent, owned

    def __getattr__(self, name):
        return getattr(tempfile, name)

    def TemporaryDirectory(self, *args, **kwargs):
        require(kwargs.get("dir") is None, "fixture cannot substitute an unowned scratch root")
        kwargs["dir"] = self.parent
        directory = tempfile.TemporaryDirectory(*args, **kwargs)
        self.owned.append(directory)
        return directory


class ImportedGuards:
    """Private source fixtures, explicitly isolated from a science-loaded suite."""

    def __init__(self, source: Path, roots: dict[str, Path]) -> None:
        self.source, self.roots, self.preparation = source, roots, validate_surface(source)
        require(set(roots) == {"fit", "reproduction"}, "exact portable predecessor roles required")
        self.predecessors = {}
        for role, mapping in (("fit", FIT_PINS), ("reproduction", REPRODUCTION_PINS)):
            safe(roots[role])
            for name, pin in mapping.items():
                path = roots[role] / name
                require(sha(path) == pin, "immutable predecessor differs")
                self.predecessors[str(path)] = {"sha256": pin, "bytes": path.stat().st_size}
        scratch = fixture_parent()
        if scratch is not None:
            require(not any(scratch == root or scratch.is_relative_to(root) or root.is_relative_to(scratch)
                            for root in (source, *roots.values())), "test scratch overlaps immutable carrier/predecessor")
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-guard-carrier-", dir=scratch)
        self.carrier = Path(self.temporary.name).resolve() / "guarded_dispatch"
        self.private: dict[str, Any] = {}
        self.aliases: dict[str, Any] = {}
        self.tests: list[Any] = []
        self.closed = False
        self.prefix = "_portable_guard_" + uuid.uuid4().hex
        self.boundary_reports: list[dict[str, Any]] = []
        try:
            shutil.copytree(source, self.carrier)
            require(validate_surface(self.carrier) == self.preparation, "source carrier copy differs")
            self.fixture_json = FixtureJson((self.carrier / "source_bindings.json").read_text(), roots)
            for filename in TEST_ORDER:
                module = self._import(self.carrier / filename, TEST_SHA[filename], filename.removesuffix(".py"))
                self.tests.append(module)
                self.aliases[filename.removesuffix(".py")] = module
                if filename == "test_guarded_dispatch.py":
                    for alias, attribute, source_name in (("_fictional_guard_core", "g", "guard_fit_dispatch.py"),
                                                          ("_fictional_guard_capture", "c", "capture_guarded_dispatch.py")):
                        runtime = getattr(module, attribute)
                        require(sha(Path(runtime.__file__)) == SOURCE_SHA[source_name], "original fixture runtime differs")
                        if attribute == "g":
                            require(runtime.FIT_PINS == FIT_PINS and runtime.REPRODUCTION_PINS == REPRODUCTION_PINS,
                                    "original fixture predecessor law differs")
                        private = self.prefix + "_" + source_name.removesuffix(".py")
                        require(private not in sys.modules, "private runtime alias occupied")
                        self.private[private], sys.modules[private] = runtime, runtime
                        self.aliases[alias] = runtime
            self._import(self.carrier / "verify_guarded_dispatch_proof.py", SOURCE_SHA["verify_guarded_dispatch_proof.py"], "reader")
            self.original_classes = [candidate for module in self.tests for candidate in vars(module).values()
                if isinstance(candidate, type) and issubclass(candidate, unittest.TestCase) and candidate.__module__ == module.__name__]
            self.original_methods = sorted((cls.__name__, name) for cls in self.original_classes for name in unittest.defaultTestLoader.getTestCaseNames(cls))
            expected_methods = sorted([*(('GuardTests', name) for name in ORIGINAL_METHOD_AST),
                                       *(('GuardV2Regressions', name) for name in REGRESSION_METHOD_AST),
                                       *(('GuardV3ReuseConsistency', name) for name in CONSISTENCY_METHOD_AST)])
            require(self.original_methods == expected_methods and len(self.original_methods) == len(set(self.original_methods)) == 41,
                    "original23 plus regression11 plus consistency7 test collection differs or duplicates")
            require(validate_surface(source) == self.preparation and validate_surface(self.carrier) == self.preparation, "source changed during private import")
        except BaseException:
            self.close()
            raise
        atexit.register(self.close)

    def _import(self, path: Path, expected: str, role: str) -> Any:
        name = self.prefix + "_" + role
        require(name not in sys.modules and sha(path) == expected, "private source/namespace differs")
        specification = importlib.util.spec_from_file_location(name, path)
        require(specification is not None and specification.loader is not None, "private loader unavailable")
        module = importlib.util.module_from_spec(specification)
        self.private[name], sys.modules[name] = module, module
        with self.scope():
            specification.loader.exec_module(module)
        require(sha(path) == expected, "source changed during private import")
        return module

    @contextmanager
    def scope(self):
        baseline = dict(sys.modules)
        isolated = {name: module for name, module in baseline.items() if name in ALIASES or name == "src" or name.startswith("src.")}
        for name in isolated:
            sys.modules.pop(name)
        visible_science = science_names()
        owned_tempdirs, process_calls, import_calls = [], [], []
        original_import = builtins.__import__

        def blocked_process(*args, **kwargs):
            process_calls.append(repr(args[:1]))
            raise InvalidFixture("actual subprocess/process forbidden in source fixtures")

        def guarded_import(name, *args, **kwargs):
            if any(name == prefix or name.startswith(prefix + ".") for prefix in SCIENCE_PREFIXES):
                import_calls.append(name)
                raise InvalidFixture("scientific import forbidden in source fixtures: " + name)
            return original_import(name, *args, **kwargs)

        introduced_science = set()
        try:
            with ExitStack() as stack:
                stack.enter_context(patch.object(sys, "path", list(sys.path)))
                stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
                stack.enter_context(patch.dict(os.environ, {name: "1" for name in THREADS}))
                stack.enter_context(patch.object(builtins, "__import__", guarded_import))
                # Leave subprocess.run itself unchanged: original production
                # predicates compare its identity and bind it as a default.
                # Popen is the process-creation boundary used by all those
                # stdlib helpers, including previously bound default callables.
                stack.enter_context(patch.object(subprocess, "Popen", blocked_process))
                for name in ("system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe"):
                    if hasattr(os, name):
                        stack.enter_context(patch.object(os, name, blocked_process))
                stack.enter_context(patch.dict(sys.modules, self.aliases))
                for module in self.tests:
                    if hasattr(module, "json"):
                        stack.enter_context(patch.object(module, "json", self.fixture_json))
                    if hasattr(module, "tempfile"):
                        stack.enter_context(patch.object(module, "tempfile", FixtureTempfile(Path(self.temporary.name), owned_tempdirs)))
                try:
                    yield
                finally:
                    introduced_science = science_names() - visible_science
        finally:
            temp_paths = [str(directory.name) for directory in owned_tempdirs]
            for directory in reversed(owned_tempdirs):
                directory.cleanup()
            for name in set(sys.modules) - set(baseline):
                if name.startswith(OWNED_FIXTURE_PREFIXES) or name in ALIASES or name == "src" or name.startswith("src."):
                    sys.modules.pop(name, None)
            for name in ALIASES:
                if name not in baseline:
                    sys.modules.pop(name, None)
            sys.modules.update(isolated)
            report = {"temporarily_isolated_src_names": sorted(name for name in isolated if name == "src" or name.startswith("src.")),
                      "introduced_scientific_names": sorted(introduced_science), "blocked_process_calls": process_calls,
                      "blocked_scientific_import_calls": import_calls, "owned_tempdirs_removed": all(not Path(name).exists() for name in temp_paths)}
            self.boundary_reports.append(report)
            require(all(sys.modules.get(name) is value for name, value in isolated.items()), "caller alias/src identity was not restored")
            require(not introduced_science and not process_calls and not import_calls, "fixture attempted a scientific import/process or introduced science")
            require(report["owned_tempdirs_removed"], "failed fixture cleanup leaked an owned directory")

    def export(self, namespace: dict[str, Any]) -> None:
        imported = self

        class ScopedRun:
            def run(self, result=None):
                with imported.scope():
                    return super().run(result)

        for original in self.original_classes:
            name = "TestRetainedGuard" + original.__name__
            require(name not in namespace, "original class exported twice")
            exported = type(name, (ScopedRun, original), {"__module__": namespace["__name__"]})
            for method in unittest.defaultTestLoader.getTestCaseNames(original):
                require(getattr(exported, method) is getattr(original, method), "original method object rewritten")
            namespace[name] = exported

    def report(self) -> dict[str, Any]:
        require(validate_surface(self.source) == self.preparation and validate_surface(self.carrier) == self.preparation, "original or fixture carrier differs")
        return {"status": "guard_complete_carrier_source_only_fixture_verified", "preparation_sha256": PREPARATION_SHA,
                "runtime_source_sha256": SOURCE_SHA, "test_source_sha256": TEST_SHA,
                "complete_carrier_members": CARRIER_MEMBERS, "complete_carrier_directories": list(CARRIER_DIRECTORIES),
                "original_method_ast_sha256": ORIGINAL_METHOD_AST,
                "regression_method_ast_sha256": REGRESSION_METHOD_AST, "consistency_method_ast_sha256": CONSISTENCY_METHOD_AST,
                "retained_methods": self.original_methods, "fixture_source_bindings_resolution": "exact_repository_relative_byte_pinned_roles_only",
                "actual_subprocess_controller_checker_generator_model_score_or_approval_invoked": False}

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for name, module in self.private.items():
            if sys.modules.get(name) is module:
                sys.modules.pop(name)
        self.temporary.cleanup()
        atexit.unregister(self.close)
