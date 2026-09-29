"""Pure fictional location/input/carrier guards; no actual science/owners."""
from __future__ import annotations

import ast
import copy
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fictional_support as fixture
import location_core as loc
import receiving_at_locations as receiving
import selected_at_locations as selected
import test_capture_locations as captests


class LocationGuards(unittest.TestCase):
    def setUp(self):
        self.case=captests.OriginalCaptureTests('test_single_fixed_identity_synthetic_capture_retains_failures_without_reviews')
        self.case.setUp()
        self.identity=self.case.identity

    def tearDown(self):
        self.case.tearDown()

    def validate(self, previous=None):
        t=self.case
        loc.validate_plan(t.plan,selection=t.selection,selection_sha=t.request['selected_reproduction_selection']['sha256'],
            scope_sha='s'*64,original=t.context['original'],inventory=t.inventory,base=t.base_evidence,
            choice=t.choice,audit=t.audit,adapter_pins=t.preparation['implementation_source_sha256'],previous=previous)

    def locations(self, path=None, resolve=None):
        t=self.case
        return loc.Locations(path or t.plan_path,loc.io.sha(path or t.plan_path),t.preparation,
            selection=t.selection,selection_sha=t.request['selected_reproduction_selection']['sha256'],scope_sha='s'*64,
            original=t.context['original'],inventory=t.inventory,base=t.base_evidence,freeze=t.freeze,resolve=resolve)

    def test_valid_pending_only_plan_keeps_order_and_default(self):
        self.validate()
        locations=self.locations()
        self.assertEqual(locations.actual(self.identity),self.case.output)
        self.assertEqual(locations.historical(self.identity),self.case.output)
        self.assertEqual(locations.actual(self.case.ordered[0]),Path(self.case.selection['paths']['original_reproduction']))
        self.assertEqual(locations.metadata(self.identity)['original_plan_selected_index'],8)

    def test_scientific_selection_definition_inventory_scope_and_legacy_pins_refuse(self):
        baseline=copy.deepcopy(self.case.plan)
        for key in ('selection_sha256','scope_definition_sha256','input_inventory_sha256','definition_content_sha256',
                    'original_numerical_evidence_sha256','original_manifest_sha256'):
            with self.subTest(key=key):
                self.case.plan=copy.deepcopy(baseline)
                self.case.plan[key]='f'*64
                with self.assertRaises(ValueError):
                    self.validate()
        self.case.plan=copy.deepcopy(baseline)
        self.case.plan['legacy_source_sha256']['selected']['reproduction_core.py']='f'*64
        with self.assertRaises(ValueError):
            self.validate()

    def test_known_verified_evidence_is_not_replaceable(self):
        self.case.base_evidence['entries'][self.identity]['status']='verified_original_numerical_reproduction_evidence'
        with self.assertRaisesRegex(ValueError,'known evidence'):
            self.validate()

    def test_changed_terminal_unresolved_inputs_refuse(self):
        row=next(r for r in self.case.inventory['entries'] if r['original_cell_id']==self.identity)
        for action in ('fit_changed_inputs','retune_then_fit_changed_inputs','retain_input_failure','unresolved','await_original_outcome'):
            with self.subTest(action=action):
                row['decision']['action']=action
                with self.assertRaises(ValueError):
                    self.validate()

    def test_wrong_witness_and_pending_hash_refuse(self):
        row=self.case.plan['entry_locations'][self.identity]
        for key in ('pending_base_entry_sha256','current_input_witness_sha256'):
            before=row[key]
            row[key]='f'*64
            with self.assertRaises(ValueError):
                self.validate()
            row[key]=before

    def test_only_original92_not_pilot_only_or_arbitrary_can_move(self):
        row=self.case.plan['entry_locations'].pop(self.identity)
        pilot=self.case.original_manifest['plan'][92]['cell_id']
        self.case.selection['pilot_cells']=[pilot]
        self.case.selection['selected_cells']=sorted(set(self.case.ordered)|{pilot})
        self.case.plan['entry_locations'][pilot]={**row,'original_cell_id':pilot}
        self.case.choice['selected_missing_producer_cell_ids']=[pilot]
        with self.assertRaisesRegex(ValueError,'unproven inherited subset'):
            self.validate()

    def test_missing_or_wrong_root_review_does_not_authorise_paths(self):
        self.case.plan['reviewer_role']='agent'
        with self.assertRaises(ValueError):
            self.validate()
        self.case.plan['reviewer_role']='root'
        self.case.audit['entries'][self.identity]['default_original_reproduction_owner_finished']=False
        with self.assertRaisesRegex(ValueError,'default-owner'):
            self.validate()

    def test_source_score_or_automatic_all92_refuse(self):
        for key in ('source_score_selection','automatic_all92_rerun'):
            with self.subTest(key=key):
                self.case.choice[key]=True
                with self.assertRaises(ValueError):
                    self.validate()
                self.case.choice[key]=False

    def test_bool_worker_wrong_index_wrong_count_and_wrong_route_refuse(self):
        row=self.case.plan['entry_locations'][self.identity]
        for key,value in (('original_plan_selected_index',True),('original_plan_selected_index',83),
                          ('workers',True),('workers',91),('producer_route','reviewed_external_prestage')):
            with self.subTest(key=key,value=value):
                before=row[key]
                row[key]=value
                with self.assertRaisesRegex(ValueError,'plan-order'):
                    self.validate()
                row[key]=before

    def test_overlapping_duplicate_relative_or_symlink_locations_refuse(self):
        row=self.case.plan['entry_locations'][self.identity]
        before=row['capture_root']
        for value in (row['historical_reproduction_root'],row['historical_reproduction_root']+'/nested','relative'):
            row['capture_root']=value
            with self.assertRaises(ValueError):
                self.validate()
        link=self.case.base/'link'
        link.symlink_to(self.case.source)
        row['capture_root']=str(link/'capture')
        with self.assertRaisesRegex(ValueError,'linked'):
            self.validate()
        row['capture_root']=before

    def test_append_only_preserves_prior_root_and_scope(self):
        previous=copy.deepcopy(self.case.plan)
        self.case.plan['previous_plan']={'path':'/fictional/previous.json','sha256':'a'*64}
        self.validate(previous)
        self.case.plan['entry_locations'][self.identity]['capture_root']=str(self.case.base/'replacement')
        with self.assertRaisesRegex(ValueError,'replace'):
            self.validate(previous)

    def test_append_only_new_pending_identity_without_replacing_old(self):
        previous=copy.deepcopy(self.case.plan)
        identity=self.case.ordered[7]
        entry=next(r for r in self.case.inventory['entries'] if r['original_cell_id']==identity)
        old=self.case.plan['entry_locations'][self.identity]
        pending=loc.io.canonical(self.case.base_evidence['entries'][identity])
        self.case.plan['previous_plan']={'path':'/fictional/previous.json','sha256':'a'*64}
        self.case.plan['entry_locations'][identity]={**old,'original_cell_id':identity,'pending_base_entry_sha256':pending,
            'current_input_witness_sha256':entry['input_witness_sha256'],'capture_root':str(self.case.base/'second_capture'),
            'historical_reproduction_root':str(self.case.base/'second_refit'),'original_plan_selected_index':7}
        self.case.choice['selected_missing_producer_cell_ids']=sorted([self.identity,identity])
        self.case.audit['entries'][identity]={**self.case.audit['entries'][self.identity],'pending_base_entry_sha256':pending,
            'current_input_witness_sha256':entry['input_witness_sha256']}
        self.validate(previous)

    def appended(self):
        t=self.case
        identity=t.ordered[7]
        entry=next(r for r in t.inventory['entries'] if r['original_cell_id']==identity)
        plan=copy.deepcopy(t.plan)
        plan['historical_plan_path']=str(t.base/'appended.json')
        plan['previous_plan']={'path':str(t.plan_path),'sha256':loc.io.sha(t.plan_path)}
        pending=loc.io.canonical(t.base_evidence['entries'][identity])
        plan['entry_locations'][identity]={**plan['entry_locations'][self.identity],
            'original_cell_id':identity,'pending_base_entry_sha256':pending,
            'current_input_witness_sha256':entry['input_witness_sha256'],'capture_root':str(t.base/'second_capture'),
            'historical_reproduction_root':str(t.base/'second_refit'),'original_plan_selected_index':7}
        choice=copy.deepcopy(t.choice)
        choice['selected_missing_producer_cell_ids']=sorted([self.identity,identity])
        audit=copy.deepcopy(t.audit)
        audit['entries'][identity]={**audit['entries'][self.identity],
            'pending_base_entry_sha256':pending,'current_input_witness_sha256':entry['input_witness_sha256']}
        for key,name,value in (('root_missing_producer_choice','appended_choice.json',choice),
                               ('actual_producer_audit','appended_audit.json',audit)):
            path=t.base/name
            plan[key]={'path':str(path),'sha256':fixture.write(path,value)}
        path=t.base/'appended.json'
        fixture.write(path,plan)
        return path,identity,plan

    def test_loaded_append_history_preserves_first_introducing_sha_and_old_record(self):
        before=self.locations()
        path,new_identity,_=self.appended()
        after=self.locations(path)
        self.assertEqual(after.metadata(self.identity),before.metadata(self.identity))
        self.assertEqual(after.metadata(new_identity)['location_plan_sha256'],loc.io.sha(path))
        after.verify_envelope(before.envelope(),self.identity)
        after.verify_envelope(before.envelope(),self.case.ordered[0])
        with self.assertRaisesRegex(ValueError,'same per-entry'):
            after.verify_envelope(before.envelope(),new_identity)
        after.recheck()

    def test_loaded_prior_plan_historical_role_and_changed_prior_bytes_refuse(self):
        path,_,plan=self.appended()
        prior=copy.deepcopy(self.case.plan)
        prior['historical_plan_path']=str(self.case.base/'wrong_previous.json')
        plan['previous_plan']['sha256']=fixture.write(self.case.plan_path,prior)
        fixture.write(path,plan)
        with self.assertRaisesRegex(ValueError,'prior plan file'):
            self.locations(path)

    def test_record_envelope_unknown_plan_changed_sources_or_rewritten_selection_refuse(self):
        locations=self.locations()
        for key,value in (('location_plan_sha256','f'*64),('selection_bytes_rewritten',True),
                          ('io_adapter_source_sha256',{}),('location_plan_path','/fictional/copied-plan.json')):
            with self.subTest(key=key):
                envelope=copy.deepcopy(locations.envelope())
                envelope[key]=value
                with self.assertRaises(ValueError):
                    locations.verify_envelope(envelope,self.identity)

    def test_changed_plan_bytes_witness_bytes_and_preparation_fail_rechecks(self):
        locations=self.locations()
        self.case.plan_path.write_text('changed fictional byte\n')
        with self.assertRaises(ValueError):
            locations.recheck()

    def test_overlap_with_frozen_or_default_root_refused_even_when_plan_is_pinned(self):
        self.case.plan['entry_locations'][self.identity]['historical_reproduction_root']=str(self.case.original/'new')
        fixture.write(self.case.plan_path,self.case.plan)
        with self.assertRaisesRegex(ValueError,'overlap'):
            self.locations()

    def test_default_active_owner_prevents_capture_not_hidden_by_alternate(self):
        root=Path(self.case.selection['paths']['original_reproduction'])
        fixture.write(root/'claims'/(self.identity+'.json'),{'fictional_owner':True})
        locations=self.locations()
        with self.assertRaisesRegex(ValueError,'owner still active'):
            locations.fresh(self.identity,self.case.output,self.case.capture_root)

    def test_root_not_declared_is_not_fallback_or_copy_equivalence(self):
        locations=self.locations()
        with self.assertRaisesRegex(ValueError,'same declared'):
            locations.fresh(self.identity,self.case.base/'copied_refit',self.case.capture_root)
        with self.assertRaisesRegex(ValueError,'same declared'):
            locations.fresh(self.case.ordered[1],self.case.output,self.case.capture_root)

    def test_resolution_requires_exact_location_and_known_default_has_no_alias(self):
        locations=self.locations()
        proof={'status':'verified_original_numerical_reproduction_evidence','reproduction_location':locations.metadata(self.identity)}
        locations.resolution(self.identity,proof)
        proof['reproduction_location']['historical_reproduction_root']=str(self.case.base/'copy')
        with self.assertRaises(ValueError):
            locations.resolution(self.identity,proof)
        with self.assertRaisesRegex(ValueError,'undeclared'):
            locations.resolution(self.case.ordered[0],proof)

    def test_receiving_relocates_only_io_preserving_plan_metadata(self):
        source=self.case.base
        restored=source.parent/(source.name+'_restored')
        try:
            shutil.copytree(source,restored)
            def resolve(text):
                path=Path(text)
                return restored/path.relative_to(source) if path.is_relative_to(source) else path
            before=self.locations()
            after=self.locations(restored/'location_plan.json',resolve)
            self.assertEqual(before.envelope(),after.envelope())
            self.assertEqual(before.metadata(self.identity),after.metadata(self.identity))
            self.assertEqual(after.actual(self.identity),restored/self.case.output.relative_to(source))
            self.assertEqual(after.historical(self.identity),self.case.output)
            after.recheck()
        finally:
            shutil.rmtree(restored,ignore_errors=True)

    def test_entire_tree_keeps_failed_orphan_files_and_empty_dirs(self):
        root=self.case.base/'tree'
        (root/'empty').mkdir(parents=True)
        (root/'orphan.failed').write_bytes(b'fictional failed bytes')
        inventory=loc.full_tree(root)
        self.assertEqual(inventory['directories'],['empty'])
        self.assertEqual(set(inventory['artifacts']),{'orphan.failed'})
        (root/'empty').rmdir()
        self.assertNotEqual(inventory,loc.full_tree(root))

    def test_recheck_refuses_added_or_removed_orphan_and_empty_directory(self):
        locations=self.locations()
        root=self.case.base/'retained'
        (root/'empty').mkdir(parents=True)
        orphan=root/'orphan.failed'
        orphan.write_bytes(b'fictional failed retained ordinary bytes')
        locations.retain_tree(root)
        for added in (root/'new-empty',root/'new-orphan.failed'):
            with self.subTest(path=added.name):
                if added.suffix:
                    added.write_bytes(b'new fictional orphan')
                else:
                    added.mkdir()
                with self.assertRaisesRegex(ValueError,'inventory'):
                    locations.recheck()
                if added.is_dir():
                    added.rmdir()
                else:
                    added.unlink()
                locations.recheck()
        (root/'empty').rmdir()
        with self.assertRaisesRegex(ValueError,'inventory'):
            locations.recheck()
        (root/'empty').mkdir()
        orphan.write_bytes(b'changed fictional orphan')
        with self.assertRaisesRegex(ValueError,'changed'):
            locations.recheck()

    def test_empty_retained_root_cannot_be_replaced_by_a_symlink(self):
        locations=self.locations()
        root=self.case.base/'empty-retained'
        root.mkdir()
        locations.retain_tree(root)
        root.rmdir()
        other=self.case.base/'other-empty'
        other.mkdir()
        root.symlink_to(other,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'linked'):
            locations.recheck()

    def test_synthetic_capture_never_completes_acquisition(self):
        self.case.run_capture()
        locations=self.locations()
        proof={'status':'verified_original_numerical_reproduction_evidence','reproduction_location':locations.metadata(self.identity)}
        with self.assertRaisesRegex(ValueError,'genuine'):
            loc.acquired(locations,self.identity,proof)

    def test_production_receiving_api_refuses_injection_before_any_io(self):
        with self.assertRaisesRegex(ValueError,'fictional'):
            receiving.verify(Path('/missing'), 'f'*64,Path('/missingplan'),'f'*64,Path('/missingoutput'),Path('/missingpython'),{},dependencies={})

    def test_preparation_false_actual_scope_flags_and_honest_exact_eight_sources(self):
        prepared=copy.deepcopy(self.case.preparation)
        path=self.case.base/'bad_preparation.json'
        for key,value in (('actual_science_executed',True),('actual_subset_or_reviews_created',True),
                          ('implementation_source_sha256',loc.LEGACY['selected'])):
            with self.subTest(key=key):
                changed={**prepared,key:value}
                pin=fixture.write(path,changed)
                with self.assertRaisesRegex(ValueError,'preparation'):
                    loc.preparation(path,pin)

    def test_clis_have_no_injection_arbitrary_command_resume_or_review_creation_flags(self):
        root=Path(loc.__file__).absolute().parent
        forbidden={'--test-only','--dependencies','--invoke','--command','--all92','--resume','--make-review'}
        for name in ('capture_original_at_location.py','run_selected_at_locations.py','verify_restored_at_locations.py'):
            with self.subTest(name=name):
                tree=ast.parse((root/name).read_text())
                values={node.value for node in ast.walk(tree) if isinstance(node,ast.Constant) and isinstance(node.value,str)}
                self.assertFalse(values & forbidden)


class RoutingGuards(unittest.TestCase):
    def fake_locations(self):
        class Fake:
            default=Path('/fictional/default')
            value={'entry_locations':{'id':{}}}
            def actual(self,identity): return Path('/fictional/restored/id')
            def historical(self,identity): return Path('/fictional/upstream/id')
            def metadata(self,identity): return {'original_cell_id':identity,'location_plan_sha256':'p'*64}
            def envelope(self): return {'location_plan_sha256':'p'*64,'fictional_only':True}
            def verify_envelope(self,value,identity):
                if value != self.envelope():
                    raise ValueError('fictional envelope differs')
            def owner_clear(self,identity): return None
            def recheck(self): return None
        return Fake()

    def test_source_inherited_delegates_same_exact_root_and_restores_on_raise(self):
        locations=self.fake_locations()
        observations=[]
        class Legacy:
            class Controller:
                def inherited(self,identity,baseline,evidence):
                    observations.append(self.repro_paths['original_reproduction'])
                    raise ValueError('fictional unchanged producer gate failure')
        cls=selected.controller_class(Legacy,locations)
        instance=object.__new__(cls)
        instance.repro_paths={'original_reproduction':Path('/fictional/default')}
        instance.common=SimpleNamespace(acquisitions={})
        with patch.object(loc,'acquired',return_value={'fictional_proof_only':True}):
            with self.assertRaisesRegex(ValueError,'unchanged producer'):
                instance.inherited('id',{}, {})
        self.assertEqual(observations,[locations.actual('id')])
        self.assertEqual(instance.repro_paths['original_reproduction'],locations.default)

    def test_receiving_uses_historical_producer_root_and_restored_array_root(self):
        locations=self.fake_locations()
        observations=[]
        class Legacy:
            class ReceivingVerifier:
                def inherited(self,identity,record,baseline):
                    observations.append((self.repro_paths['original_reproduction'],self.selection['paths']['original_reproduction']))
                    return {'fictional_only':True}
        cls=receiving.verifier_class(Legacy,locations)
        instance=object.__new__(cls)
        instance.numerical={'id':{}}
        instance.repro_paths={'original_reproduction':locations.default}
        original={'paths':{'original_reproduction':str(locations.default)},'selected_cells':['id']}
        instance.selection=original
        record={'location_extension':locations.envelope(),'reproduction_location':locations.metadata('id'),
            'retained_per_entry_trees':{'fictional_only':True}}
        with patch.object(loc,'acquired',return_value={'fictional_only':True}):
            result=instance.inherited('id',record,{})
        self.assertEqual(observations,[(locations.actual('id'),str(locations.historical('id')))])
        self.assertIs(instance.selection,original)
        self.assertEqual(instance.repro_paths['original_reproduction'],locations.default)
        self.assertEqual(result['reproduction_location'],locations.metadata('id'))

    def test_receiving_restores_path_views_when_legacy_science_rejects(self):
        locations=self.fake_locations()
        class Legacy:
            class ReceivingVerifier:
                def inherited(self,*args): raise ValueError('fictional sample array mismatch')
        cls=receiving.verifier_class(Legacy,locations)
        instance=object.__new__(cls)
        instance.numerical={'id':{}}
        instance.repro_paths={'original_reproduction':locations.default}
        original={'paths':{'original_reproduction':str(locations.default)}}
        instance.selection=original
        record={'location_extension':locations.envelope(),'reproduction_location':locations.metadata('id')}
        with patch.object(loc,'acquired',return_value={}):
            with self.assertRaisesRegex(ValueError,'sample array mismatch'):
                instance.inherited('id',record,{})
        self.assertIs(instance.selection,original)
        self.assertEqual(instance.repro_paths['original_reproduction'],locations.default)

    def test_publishing_lineage_adds_no_scientific_changes_and_overwrite_refuses(self):
        t=captests.OriginalCaptureTests('test_single_fixed_identity_synthetic_capture_retains_failures_without_reviews')
        t.setUp()
        try:
            locations=loc.Locations(t.plan_path,loc.io.sha(t.plan_path),t.preparation,selection=t.selection,
                selection_sha=t.request['selected_reproduction_selection']['sha256'],scope_sha='s'*64,
                original=t.context['original'],inventory=t.inventory,base=t.base_evidence,freeze=t.freeze)
            output=t.base/'selected_output'
            (output/'cells').mkdir(parents=True)
            common=SimpleNamespace(seal=loc.io.seal,write_new=loc.io.write_new,require=loc.io.require)
            proxy=selected.PublishingCommon(common,output,locations)
            identity=t.ordered[0]
            value=loc.io.seal({'original_cell_id':identity,'status':'new_corrected_numerical_reproduction',
                'comparison':{'fictional_scientific_value':1},'external_artifacts':{},'fictional_only':True})
            path=output/'cells'/(identity+'.json')
            proxy.write_new(path,value)
            after=loc.io.read(path)
            self.assertEqual(after['comparison'],value['comparison'])
            self.assertEqual(after['status'],value['status'])
            self.assertIsNone(after['reproduction_location'])
            self.assertEqual(after['location_extension'],locations.envelope())
            with self.assertRaises(ValueError):
                proxy.write_new(path,value)
        finally:
            t.tearDown()


if __name__=='__main__':
    unittest.main()
