import {ensure} from './validation.mjs';
export const EVAL_SCOPES=Object.freeze(['private_local_evaluation','hosted_ci_evaluation']);
const notice='examples/spineboy/license.txt';
export function validateUsagePolicy(manifest,scope) {
  const policy=manifest?.license;
  ensure(EVAL_SCOPES.includes(scope)||scope==='redistributable_product_asset','LICENSE_SCOPE_INVALID');
  ensure(policy&&policy.usage_scope===scope,'LICENSE_SCOPE_MISMATCH');
  const rt=policy.runtime_rights,assets=policy.asset_rights;
  ensure(rt&&assets&&typeof rt.evidence==='string'&&rt.evidence.startsWith('https://'),
    'SPINE_RUNTIME_RIGHTS_UNVERIFIED');
  if(rt.route==='official_example_evaluation') {
    ensure(EVAL_SCOPES.includes(scope)&&
      rt.evidence.includes('github.com/EsotericSoftware/spine-runtimes')&&
      policy.purpose==='noncommercial_runtime_feasibility_only',
      'OFFICIAL_EXAMPLE_NOT_FOR_PRODUCT_INTEGRATION');
    ensure(assets.route==='official_spineboy_example' &&
      assets.noncommercial_only===true&&assets.notice_file==='license.txt' &&
      /^[0-9a-f]{64}$/.test(assets.notice_sha256??'')&&
      typeof assets.evidence==='string'&&assets.evidence.endsWith(notice),
      'OFFICIAL_EXAMPLE_ASSET_RIGHTS_INVALID');
    if(scope==='hosted_ci_evaluation')
      ensure(assets.ci_redistribution_with_notice===true,'CI_ASSET_PUBLICATION_NOT_AUTHORIZED');
  } else if(rt.route==='licensed_editor') {
    ensure(rt.operator_editor_license_verified===true &&
      typeof rt.license_record_reference==='string'&&!!rt.license_record_reference,
      'OPERATOR_LICENSE_NOT_CONFIRMED');
    ensure(assets.usage_authorized===true && !!assets.evidence,'RIG_USE_RIGHTS_UNVERIFIED');
    if(scope==='hosted_ci_evaluation')
      ensure(assets.hosted_ci_authorized===true,'HOSTED_CI_RIGHTS_UNVERIFIED');
    if(scope==='redistributable_product_asset')
      ensure(assets.redistribution_authorized===true,'REDISTRIBUTION_RIGHTS_UNVERIFIED');
  } else ensure(false,'SPINE_RUNTIME_LICENSE_ROUTE_UNKNOWN');
  return true;
}
