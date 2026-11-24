# V3 CURRENT native generated state — review-only experiment

This is NOT a verified proof of C1/RH. It fixes the previous V2 run's
source-generation mismatch by using native main commit
bb7c8184a135b2823c6296917c5ac893bebf2a71, tree
2b19357e1b65cc500f3e3a5b5d4df14601b02062, and compares with the
frozen V2 artifact from workflow 45051273111. The old artifact/candidate
is immutable, and no old generated patch is automatically transplanted.

The independent native worktree is preflight-checked for cleanliness, source,
toolchain, and exactly the 77 declared active generated products.
The legacy REGISTERED_DECLARATION_DEPENDENCIES index and three dated
historical generated products are frozen (four protected current-tree files).
All four are checked against pinned Git blobs at entry and after BOTH write
and check. Any modified non-generated tracked file or untracked output fails. The existing transactional
RHRC materializer runs --write then --check in a single owned native
environment. Both operation logs and identical generated-product bytes are
required, and the resulting patch is REVIEW ONLY.

The V2 original 29-file patch SHA256
85f0ef7476af766125ddbf07b1abef3e42a122668f6ffacf43286374acbd27d2
and old 78 product hashes are authenticated before comparison. This does
not require that V3 have the same changed paths or hashes, because its source
epoch differs. A match is regression information; a difference requires
source-level investigation.

A success of this workflow establishes only that the native writer/checker
generated a coherent candidate over current native source. Source promotion
requires human review, a separately frozen source policy, and fresh
compiler/type/axiom/independent gates at the promoted native head.

V3 additionally reopens all 17 immutable historical Git blobs (16 shards plus index) at frozen historical commit bf75a3... and verifies their full bytes against Git OIDs. This is distinct from the four protected current-tree files. The earlier logical historical index digest is not re-computed here; no new compiler certificate is claimed.
