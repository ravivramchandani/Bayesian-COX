"""Ordinary fictional JSON/byte fixture support; no science or real outcomes."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import location_core as loc

BASE = Path('/Users/macuser/bayes-cox-runs/extensions-20260928')
ROOTS = {'selected': BASE/'generator_correction_reproduction_v1',
         'receiving': BASE/'generator_correction_reproduction_restore_v1',
         'capture': BASE/'generator_correction_original_producer_completion_v1'}


def write(path: Path, value: Any, field: str | None = 'content_sha256') -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    value = copy.deepcopy(value)
    if field is not None:
        value.pop(field, None)
        value[field] = loc.io.canonical(value)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False)+'\n')
    return loc.io.sha(path)


def enrich(test: Any) -> None:
    """Add truthful fictional boundaries to the old stdlib capture fixture."""
    selection = loc.io.read(test.selection_path)
    selection['paths']['original_reproduction'] = str(test.base/'old_default_reproduction')
    selection['paths']['original_numerical_evidence'] = str(test.base/'base_evidence.json')
    selection['definition_content_sha256'] = 'd'*64
    test.inventory = {'entries': [{'original_cell_id': row['cell_id'], 'action': 'reuse_original_outcome',
        'decision': {'action': 'reuse_original_outcome'}, 'input_witness_sha256': 'a'*64,
        'input_witness_path': 'cells/'+row['cell_id']+'/input_witness.json'} for row in test.original_manifest['plan']]}
    witness = {'fictional_not_actual_input_proof': True, 'definition_content_sha256': 'd'*64}
    test.freeze = {'paths': {'source': str(test.source), 'original_run': str(test.original),
        'matched': str(test.matched), 'witness_root': str(test.base/'witness')}}
    witness_path = test.base/'witness'/'cells'/test.identity/'input_witness.json'
    witness_sha = write(witness_path,witness)
    for identity in selection['original_selected_cells']:
        write(test.base/'witness'/'cells'/identity/'input_witness.json', witness)
    for entry in test.inventory['entries']:
        if entry['original_cell_id'] in selection['original_selected_cells']:
            entry['input_witness_sha256'] = witness_sha
    inventory_sha = write(test.base/'inventory.json',test.inventory)
    test.base_evidence = {'entries': {identity: {'status': 'pending_original_numerical_reproduction',
        'fictional_not_actual_producer_inventory': True} for identity in selection['original_selected_cells']}}
    evidence_sha = write(test.base/'base_evidence.json',test.base_evidence)
    selection['input_inventory_sha256'] = inventory_sha
    selection['original_numerical_evidence_sha256'] = evidence_sha
    selection_sha = write(test.selection_path,selection)
    test.selection = loc.io.read(test.selection_path)
    test.request['selected_reproduction_selection']['sha256'] = selection_sha
    choice = loc.io.read(test.choice_path)
    choice['selection_sha256'] = selection_sha
    choice_sha = write(test.choice_path,choice)
    test.request['root_missing_producer_choice']['sha256'] = choice_sha
    test.choice = loc.io.read(test.choice_path)
    entry = next(row for row in test.inventory['entries'] if row['original_cell_id']==test.identity)
    pending_sha = loc.io.canonical(test.base_evidence['entries'][test.identity])
    test.audit = {'status': loc.AUDIT_STATUS, 'reviewer_role':'root','selection_sha256':selection_sha,
        'original_numerical_evidence_sha256':evidence_sha,'fictional_not_an_actual_review':True,
        'entries':{test.identity:{'status':'existing_actual_numerical_producer_proof_genuinely_unavailable',
            'pending_base_entry_sha256':pending_sha,'current_input_witness_sha256':witness_sha,
            'default_original_reproduction_owner_finished':True}}}
    audit_path=test.base/'audit.json'
    audit_sha=write(audit_path,test.audit)
    test.preparation.update(status='original_reproduction_per_entry_io_adapter_prepared',
        actual_science_executed=False,actual_subset_or_reviews_created=False,fictional_not_actual_preparation=True)
    prep_path=test.base/'adapter_preparation.json'
    prep_sha=write(prep_path,test.preparation)
    test.preparation=loc.io.read(prep_path,prep_sha)
    test.plan_path=test.base/'location_plan.json'
    test.plan={'schema_version':1,'status':loc.PLAN_STATUS,'reviewer_role':'root','selection_sha256':selection_sha,
        'scope_definition_sha256':'s'*64,'original_manifest_sha256':test.policy.manifest_sha,
        'input_inventory_sha256':inventory_sha,'definition_content_sha256':'d'*64,
        'original_numerical_evidence_sha256':evidence_sha,'io_adapter_source_sha256':test.preparation['implementation_source_sha256'],
        'legacy_source_sha256':loc.LEGACY,'legacy_code_roots':{key:str(path) for key,path in ROOTS.items()},
        'historical_plan_path':str(test.plan_path),'io_adapter_preparation':{'path':str(prep_path),'sha256':prep_sha},
        'root_missing_producer_choice':{'path':str(test.choice_path),'sha256':choice_sha},
        'actual_producer_audit':{'path':str(audit_path),'sha256':audit_sha},'previous_plan':None,
        'fictional_not_an_actual_location_review':True,'entry_locations':{test.identity:{'original_cell_id':test.identity,
            'pending_base_entry_sha256':pending_sha,'current_input_witness_sha256':entry['input_witness_sha256'],
            'historical_reproduction_root':str(test.output),'capture_root':str(test.capture_root),
            'original_plan_selected_index':8,'workers':92,'producer_route':'official_fresh_refit'}}}
    plan_sha=write(test.plan_path,test.plan)
    test.request['location_plan']={'path':str(test.plan_path),'sha256':plan_sha}
    test.context={'selection':test.selection,'original':loc.io.read(test.original/'manifest.json',field='manifest_content_sha256'),
        'rc':SimpleNamespace(scope_definition=lambda _:'s'*64),'inventory':test.inventory,'evidence':test.base_evidence,
        'freeze':test.freeze,'verify_inherited_input':lambda identity: test.assertEqual(identity,test.identity)}
