const path = require("path");
const T = require(path.resolve(__dirname, "..", "..", "viewer", "app.js"));

function assert(cond, msg) {
  if (!cond) throw new Error("FAIL: " + msg);
  console.log("ok -", msg);
}

// computeDomain
const feats = [
  { properties: { velocity_2026: 0.01 } },
  { properties: { velocity_2026: 0.05 } },
  { properties: { velocity_2026: null } },
  { properties: { velocity_2026: 0.1 } },
];
const dom = T.computeDomain(feats, "velocity_2026");
assert(dom.min <= 0.01 && dom.max >= 0.05, "computeDomain ignores nulls and spans real values, got " + JSON.stringify(dom));

// logistic model sanity
const F_at_t0 = T.logistic(2020, 0.8, 0.4, 2020);
assert(Math.abs(F_at_t0 - 0.4) < 1e-9, "logistic(t0) == K/2, got " + F_at_t0);

const v_at_t0 = T.velocityFromF(F_at_t0, 0.8, 0.4);
assert(Math.abs(v_at_t0 - (0.4 * 0.8) / 4) < 1e-9, "peak velocity r*K/4, got " + v_at_t0);

// sampleFittedCurve monotonic increasing for a growth curve
const curve = T.sampleFittedCurve(0.8, 0.4, 2020, 2010, 2030, 50);
let increasing = true;
for (let i = 1; i < curve.F.length; i++) if (curve.F[i] < curve.F[i - 1] - 1e-9) increasing = false;
assert(increasing, "fitted S-curve F(t) is monotonic increasing");

// topAccelerating
const accelFeats = [
  { properties: { tier: "tier1", acceleration_2026: 0.001, h3_index: "a" } },
  { properties: { tier: "tier1", acceleration_2026: 0.01, h3_index: "b" } },
  { properties: { tier: "tier2", acceleration_2026: 0.02, h3_index: "c" } }, // excluded: not tier1
  { properties: { tier: "tier1", acceleration_2026: null, h3_index: "d" } }, // excluded: null
];
const top = T.topAccelerating(accelFeats, 10);
assert(top.length === 2, "topAccelerating filters to tier1 with finite acceleration, got " + top.length);
assert(top[0].properties.h3_index === "b", "topAccelerating sorts descending, got " + top[0].properties.h3_index);

// color expressions don't throw and produce arrays (basic shape check)
const velExpr = T.velocityColorExpression({ min: 0, max: 1 });
assert(Array.isArray(velExpr) && velExpr[0] === "case", "velocityColorExpression returns a case[] expression");

const accExpr = T.accelerationColorExpression({ min: -0.01, max: 0.02 });
assert(Array.isArray(accExpr) && accExpr[0] === "case", "accelerationColorExpression returns a case[] expression");

const lifeExpr = T.lifecycleColorExpression();
assert(lifeExpr[0] === "match" && lifeExpr.includes("Saturated"), "lifecycleColorExpression is a match[] covering all categories");

const buildResult = T.buildColorExpression("lifecycle", []);
assert(buildResult.domain === null, "lifecycle layer has no numeric domain");

console.log("\nALL VIEWER LOGIC TESTS PASSED");
