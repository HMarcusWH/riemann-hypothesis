#!/usr/bin/env python3
"""Read-only compatibility and adversarial controls; never rebuilds the closure."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types

import bootstrap_native as b


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate',type=Path,required=True)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--integration',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--actual-audit-log',type=Path,required=True)
    args=parser.parse_args()
    spec=importlib.util.spec_from_file_location('unchanged_combined_gate',args.gate)
    gate_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate_module)
    gate_spec=json.loads((args.gate.parent/'GATE_SPEC.json').read_text())
    historical=json.loads((args.integration/'NATIVE_COMMON_PIN_BUILD.json').read_text())
    results=[]

    def case(name,action,reject=False):
        try:
            detail=action()
        except (b.Failure,gate_module.GateFailure) as exc:
            if not reject:raise
            results.append({'name':name,'status':'PASS_EXPECTED_REJECTION','reason':str(exc)})
        else:
            if reject:raise AssertionError('Invalid input accepted: '+name)
            results.append({'name':name,'status':'PASS','detail':detail})

    with tempfile.TemporaryDirectory(prefix='native-bootstrap-controls-') as temp:
        root=Path(temp)
        def check_receipt(data,label):
            fixture=root/(label+'.json');b.write_json(fixture,data)
            gate=gate_module.Gate.__new__(gate_module.Gate)
            gate.args=types.SimpleNamespace(native_receipt=fixture)
            gate.spec=gate_spec;gate.native=args.native.resolve();gate.integration=args.integration.resolve()
            gate.native_lib=gate.integration/'.lake/build/lib/lean'
            gate.output=root/label;gate.output.mkdir()
            gate.receipt={'environment':{'compiler_version':b.VERSION,'import_roots':[str(gate.native_lib)]}}
            gate.input_hashes={}
            return gate.native_build_receipt()['module_count']

        augmented=copy.deepcopy(historical)
        augmented['resource_policy']={'test':'extra bootstrap fields are schema-compatible'}
        augmented['type_axiom_audit']={'test':'additional field ignored by original schema checker'}
        case('unchanged_gate_accepts_original_schema_with_bootstrap_fields',
             lambda:check_receipt(augmented,'positive'))
        bad=copy.deepcopy(augmented);bad['modules'][0]['preexisting_object']=True
        case('unchanged_gate_rejects_stale_native_object',lambda:check_receipt(bad,'stale'),True)
        bad2=copy.deepcopy(augmented);bad2['modules'].pop()
        case('unchanged_gate_rejects_incomplete_closure',lambda:check_receipt(bad2,'missing'),True)
        bad3=copy.deepcopy(augmented);bad3['modules'][0]['source_sha256']='0'*64
        case('unchanged_gate_rejects_source_mutation',lambda:check_receipt(bad3,'source'),True)
        bad4=copy.deepcopy(augmented);bad4['status']='RUNNING';bad4['exit_code']=None
        case('unchanged_gate_rejects_unfinished_build',lambda:check_receipt(bad4,'running'),True)

        actual=args.actual_audit_log.read_text()
        case('actual_nine_theorem_audit',lambda:len(b.parse_audits(actual)))
        case('audit_rejects_sorry_axiom',lambda:b.parse_audits(actual.replace('propext','sorryAx',1)),True)
        case('audit_rejects_missing_type_marker',lambda:b.parse_audits(actual.replace('NATIVE_TYPE_BEGIN','BROKEN_TYPE_BEGIN',1)),True)

        native=root/'fixture-native';native.mkdir()
        source=native/'Probe.lean';source.write_text('theorem probe : True := True.intro\n')
        integration=root/'fixture-integration';target=integration/'.lake/build/lib/lean/Probe.olean'
        target.parent.mkdir(parents=True);target.write_bytes(b'stale')
        case('compiler_refuses_preexisting_object_before_launch',
             lambda:b.compile_one(None,None,integration,None,native,'Probe',b.digest(source)),True)
        target.unlink()
        case('compiler_refuses_changed_source_before_launch',
             lambda:b.compile_one(None,None,integration,None,native,'Probe','0'*64),True)

        settings=types.SimpleNamespace(timeout=1,jobs=1,process_address_space_gb=4,
                                     aggregate_rss_mb=1000,min_free_gb=0)
        runner=b.Runner(settings,root/'watchdog')
        case('watchdog_terminates_timeout_as_failure',lambda:runner.run('timeout',
             [sys.executable,'-c','import time; time.sleep(30)'],root),True)
        runner.abort.set();runner.monitor.join(timeout=2)
        b.require(runner.monitor_error=='Global bootstrap timeout','Watchdog rejection had wrong cause')

    b.write_json(args.output,{'status':'PASS','tests':results,'count':len(results),
       'scope':'Read-only historical schema compatibility, actual narrow audit output, and adversarial bootstrap controls. Not a fresh 572-module bootstrap.',
       'gate_sha256':b.digest(args.gate),'historical_native_receipt_sha256':b.digest(args.integration/'NATIVE_COMMON_PIN_BUILD.json'),
       'bootstrap_sha256':b.digest(b.BUNDLE/'bootstrap_native.py'),'c1_closed':False,'rh_closed':False})
    print(f'{len(results)} bootstrap compatibility/failure controls PASS')


if __name__=='__main__':main()
