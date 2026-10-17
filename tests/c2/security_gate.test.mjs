import test from 'node:test';
import assert from 'node:assert/strict';
import {checkAudits,parseAudit} from '../../tools/c2_security_gate.mjs';

const lock={packages:{'node_modules/example':{version:'1.2.3'}}};
function audit(severity=null,version='1.2.3'){
  const vulnerable=Boolean(severity);
  return {
    auditReportVersion:2,
    metadata:{vulnerabilities:{total:vulnerable?1:0}},
    vulnerabilities:vulnerable?{
      example:{severity,isDirect:false,nodes:['node_modules/example'],
        via:[{source:24680,url:'https://github.com/advisories/GHSA-abcd-efgh-ijkl',
          title:'Example advisory',severity,range:'<=1.2.3'}],
        effects:[],range:'<=1.2.3',fixAvailable:false}
    }:{},
  };
}
function gate(prod,full,exceptions=[]){return checkAudits(prod,full,lock,exceptions);}
test('valid clean production and full JSON PASS',()=>{
  const result=gate(audit(),audit());
  assert.deepEqual(result.errors,[]);
});
for(const severity of ['moderate','high','critical']){
  test('unreviewed '+severity+' FAIL',()=>{
    const result=gate(audit(),audit(severity));
    assert.match(result.errors.join(' '),new RegExp('UNREVIEWED_'+severity.toUpperCase()));
  });
}
test('new unknown advisory FAIL',()=>{
  const a=audit('high');
  a.vulnerabilities.example.via[0].url=undefined;
  a.vulnerabilities.example.via[0].source=undefined;
  assert.notEqual(gate(audit(),a).errors.length,0);
});
test('malformed or missing scanner report FAIL',()=>{
  for(const bad of [undefined,null,'not json',{}, {error:{code:'ENOTFOUND'}},
    {auditReportVersion:999,metadata:{vulnerabilities:{total:0}},vulnerabilities:{}}]){
    assert.notEqual(gate(bad,audit()).errors.length,0);
  }
});
test('scanner totals disagree with findings FAIL',()=>{
  const a=audit('high');a.metadata.vulnerabilities.total=0;
  assert.match(gate(a,audit()).errors.join(' '),/count mismatch/);
});
test('installed version missing from lockfile FAIL',()=>{
  const a=audit('high');a.vulnerabilities.example.nodes=['node_modules/absent'];
  assert.match(gate(a,audit()).errors.join(' '),/missing exact lockfile version/);
});
test('exact owner-reviewed time-scoped exception only applies to listed version and advisory',()=>{
  const exception={package:'example',version:'1.2.3',
    advisory_id:'GHSA-abcd-efgh-ijkl',severity:'moderate',
    owner_approved:true,approved_by:'fixture-owner',
    exposure:'Fixture-only review',mitigation:'Fixture-only mitigation',
    review_by:'2099-01-01T00:00:00Z'};
  assert.deepEqual(gate(audit('moderate'),audit('moderate'),[exception]).errors,[]);
  assert(gate(audit('high'),audit('high'),[exception]).errors.length);
  assert(gate(audit('moderate'),audit('moderate'),[{...exception,version:'1.2.4'}]).errors.length);
  assert(gate(audit('moderate'),audit('moderate'),[{...exception,advisory_id:'GHSA-other'}]).errors.length);
  assert(gate(audit('moderate'),audit('moderate'),[{...exception,owner_approved:false}]).errors.length);
  assert(gate(audit('moderate'),audit('moderate'),[{...exception,review_by:'2000-01-01T00:00:00Z'}]).errors.length);
});
test('transitive severity propagation cannot bypass exception',()=>{
  const a=audit('high');
  a.vulnerabilities.example.via=['vulnerable-transitive'];
  const x=parseAudit(a,'full',lock,[]);
  assert(x.errors.length>0);
});
