/** Mandatory C2 dependency gate: both production and FULL installed graph.
 * npm audit exits nonzero for actual advisories; JSON must still be inspected.
 * No wildcard exception, high/critical allowance or scanner-error success.
 */
import {readFileSync,writeFileSync} from 'node:fs';
import {dirname,join} from 'node:path';

const [prodPath,fullPath]=process.argv.slice(2);
if (!prodPath || !fullPath) throw new Error('C2_SECURITY_AUDIT_INPUT_MISSING');
const lock=JSON.parse(readFileSync('package-lock.json','utf8'));
const report={schema_version:'c2.dependency_audit.v1',production:[],full:[],policy:'unknown/unreviewed high or critical block; moderate require review',exceptions:[],errors:[]};
const acceptedModerate={
  // No silent exception: add an exact advisory ID and version only after
  // an owner-approved rationale and mitigation are recorded in the C2 review.
};

function parse(path,label) {
  let payload;
  try { payload=JSON.parse(readFileSync(path,'utf8')); }
  catch(error) {report.errors.push(label+': audit JSON unavailable or malformed');return [];}
  if (payload.error || payload.auditReportVersion!==2 || !payload.metadata?.vulnerabilities || typeof payload.vulnerabilities!=='object') {
    report.errors.push(label+': scanner failed or returned unrecognized report');
    return [];
  }
  const rows=[];
  for(const [name,v] of Object.entries(payload.vulnerabilities)) {
    const advisories=(v.via||[]).filter(x=>typeof x==='object').map(x=>({
      id:x.source, title:x.title, url:x.url, severity:x.severity, range:x.range,
    }));
    const versions=[...new Set((v.nodes||[]).map(node=>lock.packages?.[node]?.version).filter(Boolean))];
    const row={
      package:name, versions, severity:v.severity, isDirect:Boolean(v.isDirect),
      nodes:v.nodes||[], via:advisories, through:(v.via||[]).filter(x=>typeof x==='string'),
      effects:v.effects||[], range:v.range, fixAvailable:v.fixAvailable,
      activeInLauncher:label==='full' && (name==='vite'||name==='@vitejs/plugin-react'||name==='esbuild'||name==='rollup') ? true : null,
    };
    rows.push(row);
    if (['high','critical'].includes(v.severity))
      report.errors.push(label+': UNREVIEWED_'+v.severity.toUpperCase()+': '+name+' '+versions.join(','));
    else if(v.severity==='moderate'){
      const keys=advisories.map(a=>String(a.id));
      const accepted=keys.length>0 && keys.every(id=>acceptedModerate[id]?.package===name && versions.every(v=>acceptedModerate[id].version===v));
      if(!accepted) report.errors.push(label+': UNREVIEWED_MODERATE: '+name+' '+versions.join(','));
    }
  }
  rows.sort((a,b)=>a.package.localeCompare(b.package));
  const reportedTotal=payload.metadata.vulnerabilities.total;
  if (typeof reportedTotal!=='number') report.errors.push(label+': missing totals');
  return rows;
}
report.production=parse(prodPath,'production');
report.full=parse(fullPath,'full');
const out=join(dirname(fullPath),'npm-security-report.json');
writeFileSync(out,JSON.stringify(report,null,2)+'\n');
console.log('C2 dependency report:',out);
console.log('C2 inventory:',JSON.stringify({production:report.production.length,full:report.full.length,issues:report.errors}));
if(report.errors.length) {
  console.error('C2_SECURITY_AUDIT_BLOCKED: '+report.errors.join('; '));
  process.exitCode=1;
}
