/** Mandatory C2 dependency gate: both production and FULL installed graph.
 * npm audit exits nonzero for actual advisories; JSON must still be inspected.
 * No wildcard exception, high/critical allowance or scanner-error success.
 */
import {readFileSync,writeFileSync} from 'node:fs';
import {dirname,join} from 'node:path';
import {pathToFileURL} from 'node:url';

const [prodPath,fullPath]=process.argv.slice(2);
const report={schema_version:'c2.dependency_audit.v2',production:[],full:[],
  policy:'unreviewed moderate/high/critical findings block both scopes; owner-approved exact exceptions only',
  exceptions:[],errors:[]};
const lockfile=()=>JSON.parse(readFileSync('package-lock.json','utf8'));
const acceptedModerate={
  // No silent exception: add an exact advisory ID and version only after
  // an owner-approved rationale and mitigation are recorded in the C2 review.
};

export function parseAudit(payload,label,lock,exceptions=[]) {
  const errors=[];
  if (!payload || payload.error || payload.auditReportVersion!==2 ||
      typeof payload.metadata?.vulnerabilities?.total!=='number' ||
      !payload.vulnerabilities || Array.isArray(payload.vulnerabilities) ||
      typeof payload.vulnerabilities!=='object') {
    return {rows:[],errors:[label+': scanner failed or returned unrecognized report']};
  }
  const rows=[];
  for(const [name,v] of Object.entries(payload.vulnerabilities)) {
    if (!v || !['info','low','moderate','high','critical'].includes(v.severity) ||
        !Array.isArray(v.via) || !Array.isArray(v.nodes) || !Array.isArray(v.effects)) {
      errors.push(label+': invalid advisory payload:'+name);
      continue;
    }
    const advisories=v.via.filter(x=>x&&typeof x==='object').map(x=>({
      id:x.url?.match(/GHSA-[a-z0-9-]+/i)?.[0]||String(x.source??''),
      title:x.title,url:x.url,severity:x.severity,range:x.range,
    }));
    const versions=[...new Set(v.nodes.map(node=>lock.packages?.[node]?.version).filter(Boolean))];
    if (!v.nodes.length || versions.length===0 || v.nodes.some(node=>!lock.packages?.[node]?.version))
      errors.push(label+': missing exact lockfile version:'+name);
    const row={
      package:name, versions, severity:v.severity, isDirect:Boolean(v.isDirect),
      nodes:v.nodes||[], via:advisories, through:(v.via||[]).filter(x=>typeof x==='string'),
      effects:v.effects||[], range:v.range, fixAvailable:v.fixAvailable,
      activeInLauncher:label==='full' && ['vite','@vitejs/plugin-react','esbuild','rollup','tailwindcss','postcss','braces','micromatch'].includes(name),
    };
    rows.push(row);

    if (['moderate','high','critical'].includes(v.severity)) {
      // Implicit transitive advisory propagation is NOT an exception.
      const ids=advisories.map(a=>a.id);
      const approved=ids.length>0 && !row.through.length && versions.length>0 &&
        ids.every(id=>versions.every(version=>exceptions.some(e=>
          e.package===name && e.version===version && e.advisory_id===id &&
          e.severity===v.severity && e.owner_approved===true &&
          typeof e.approved_by==='string' && e.approved_by.length>0 &&
          typeof e.exposure==='string' && e.exposure.length>0 &&
          typeof e.mitigation==='string' && e.mitigation.length>0 &&
          Number.isFinite(Date.parse(e.review_by)) && Date.parse(e.review_by)>Date.now())));
      if (!approved)
        errors.push(label+': UNREVIEWED_'+v.severity.toUpperCase()+': '+name+' '+versions.join(','));
    }
  }
  rows.sort((a,b)=>a.package.localeCompare(b.package));
  const reportedTotal=payload.metadata.vulnerabilities.total;
  if (!Number.isInteger(reportedTotal) || reportedTotal!==rows.length)
    errors.push(label+': scanner count mismatch or invalid total');
  return {rows,errors};
}

export function checkAudits(production,full,lock,exceptions=[]) {
  const a=parseAudit(production,'production',lock,exceptions);
  const b=parseAudit(full,'full',lock,exceptions);
  return {...report,production:a.rows,full:b.rows,errors:[...a.errors,...b.errors]};
}

if (process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href) {
  if (!prodPath || !fullPath) throw new Error('C2_SECURITY_AUDIT_INPUT_MISSING');
  function load(path) {
    try {return JSON.parse(readFileSync(path,'utf8'));}
    catch {return {error:{code:'SCANNER_OUTPUT_UNAVAILABLE'}};}
  }
  // No repository owner has approved a security exception for this C2 PR.
  const result=checkAudits(load(prodPath),load(fullPath),lockfile());
  const out=join(dirname(fullPath),'npm-security-report.json');
  writeFileSync(out,JSON.stringify(result,null,2)+'\\n');
  console.log('C2 security report:',out);
  console.log('C2 advisory counts:',JSON.stringify({production:result.production.length,full:result.full.length}));
  if(result.errors.length) {
    console.error('C2_SECURITY_AUDIT_BLOCKED:',result.errors.join('; '));
    process.exitCode=1;
  }
}
