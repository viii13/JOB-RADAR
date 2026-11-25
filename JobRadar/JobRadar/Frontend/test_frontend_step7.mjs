// JobRadar Phase 7.5 Step 7: Frontend Verification Runner
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = __dirname;
const PROJECT_ROOT = path.resolve(FRONTEND_ROOT, "../DDS-Job-Market-Project");
const DOCS_TESTING_DIR = path.resolve(PROJECT_ROOT, "docs/testing");

const results = {
  summary: { total: 0, passed: 0, failed: 0 },
  tests: {},
  build_artifacts: {},
  components_verified: [],
  api_modules_verified: [],
};

function recordTest(name, passed, details = null) {
  results.summary.total += 1;
  if (passed) {
    results.summary.passed += 1;
    console.log(`[PASS] ${name}`);
  } else {
    results.summary.failed += 1;
    console.error(`[FAIL] ${name}:`, details);
  }
  results.tests[name] = {
    status: passed ? "PASS" : "FAIL",
    details,
  };
}

async function runStep7() {
  console.log("=======================================================");
  console.log("EXECUTING STEP 7: FRONTEND COMPONENT & INTEGRATION TESTS");
  console.log("=======================================================\n");

  // 1. Build Artifact Verification
  console.log("--- 1. Build Artifacts Verification ---");
  const distDir = path.resolve(FRONTEND_ROOT, "dist");
  const htmlPath = path.resolve(distDir, "index.html");
  const assetsDir = path.resolve(distDir, "assets");

  const htmlExists = fs.existsSync(htmlPath);
  let htmlSize = 0;
  if (htmlExists) {
    htmlSize = fs.statSync(htmlPath).size;
  }
  recordTest("fe_build_html_exists", htmlExists && htmlSize > 500, { htmlSize });

  let jsBundle = null;
  let cssBundle = null;
  if (fs.existsSync(assetsDir)) {
    const files = fs.readdirSync(assetsDir);
    for (const f of files) {
      if (f.endsWith(".js")) {
        const sz = fs.statSync(path.resolve(assetsDir, f)).size;
        jsBundle = { name: f, size: sz };
      }
      if (f.endsWith(".css")) {
        const sz = fs.statSync(path.resolve(assetsDir, f)).size;
        cssBundle = { name: f, size: sz };
      }
    }
  }

  recordTest(
    "fe_build_js_bundle",
    jsBundle !== null && jsBundle.size > 500000,
    jsBundle
  );
  recordTest(
    "fe_build_css_bundle",
    cssBundle !== null && cssBundle.size > 20000,
    cssBundle
  );

  results.build_artifacts = {
    html: { path: "dist/index.html", sizeBytes: htmlSize },
    js: jsBundle,
    css: cssBundle,
  };

  // 2. Vite SSR Module Loading
  console.log("\n--- 2. Component & API Module Resolution ---");
  const { createServer } = await import("vite");
  const server = await createServer({
    root: FRONTEND_ROOT,
    server: { middlewareMode: true },
    appType: "custom",
  });

  const apiModules = [
    { path: "/src/api/client.js", expectedExports: ["request", "ApiError", "API_BASE"] },
    { path: "/src/api/analytics.js", expectedExports: ["analyticsApi"] },
    { path: "/src/api/jobs.js", expectedExports: ["jobsApi"] },
    { path: "/src/api/skills.js", expectedExports: ["skillsApi"] },
    { path: "/src/api/salary.js", expectedExports: ["salaryApi"] },
    { path: "/src/api/recommendations.js", expectedExports: ["recommendationsApi"] },
    { path: "/src/api/auth.js", expectedExports: ["authApi"] },
  ];

  for (const m of apiModules) {
    try {
      const mod = await server.ssrLoadModule(m.path);
      const keys = Object.keys(mod);
      const hasAll = m.expectedExports.every((e) => keys.includes(e));
      recordTest(`fe_load_${path.basename(m.path, ".js")}`, hasAll, { exports: keys });
      results.api_modules_verified.push({ module: m.path, exports: keys });
    } catch (err) {
      recordTest(`fe_load_${path.basename(m.path, ".js")}`, false, { error: err.message });
    }
  }

  const componentModules = [
    { path: "/src/pages/DashboardPage.jsx", name: "DashboardPage" },
    { path: "/src/pages/SkillsPage.jsx", name: "SkillsPage" },
    { path: "/src/pages/JobsPage.jsx", name: "JobsPage" },
    { path: "/src/pages/SkillGapPage.jsx", name: "SkillGapPage" },
    { path: "/src/pages/MindMapPage.jsx", name: "MindMapPage" },
    { path: "/src/pages/OnboardingPage.jsx", name: "OnboardingPage" },
    { path: "/src/pages/ProfilePage.jsx", name: "ProfilePage" },
    { path: "/src/pages/LoginPage.jsx", name: "LoginPage" },
    { path: "/src/pages/RegisterPage.jsx", name: "RegisterPage" },
    { path: "/src/pages/NotFoundPage.jsx", name: "NotFoundPage" },
    { path: "/src/components/salary/SalaryPredictorWidget.jsx", name: "SalaryPredictorWidget" },
  ];

  for (const c of componentModules) {
    try {
      const mod = await server.ssrLoadModule(c.path);
      const hasExport = mod[c.name] !== undefined || mod.default !== undefined;
      recordTest(`fe_load_component_${c.name}`, hasExport, { exports: Object.keys(mod) });
      results.components_verified.push(c.name);
    } catch (err) {
      recordTest(`fe_load_component_${c.name}`, false, { error: err.message });
    }
  }

  // 3. Centralized API Client (client.js) Unit Tests
  console.log("\n--- 3. Centralized API Client Functional Tests ---");
  const clientMod = await server.ssrLoadModule("/src/api/client.js");
  const { ApiError, API_BASE, request } = clientMod;

  // Test 3a: ApiError class properties
  const customErr = new ApiError("Validation failed", 422, [{ loc: ["body", "exp"], msg: "Invalid" }]);
  recordTest(
    "fe_client_api_error_structure",
    customErr.name === "ApiError" &&
      customErr.status === 422 &&
      customErr.message === "Validation failed" &&
      Array.isArray(customErr.detail),
    { name: customErr.name, status: customErr.status, detail: customErr.detail }
  );

  // Test 3b: API_BASE default configuration
  recordTest(
    "fe_client_api_base_url",
    API_BASE === "http://127.0.0.1:8000" || API_BASE.startsWith("http"),
    { API_BASE }
  );

  // Test 3c: Timeout / AbortController handling
  let timeoutPassed = false;
  try {
    // Request a dead blackhole IP with 100ms timeout
    await request("http://10.255.255.1/test", { timeout: 100 });
  } catch (err) {
    timeoutPassed = err.status === 408 || err.message.includes("timeout") || err.status === 0;
  }
  recordTest("fe_client_timeout_abort_handling", timeoutPassed, "Timeout or connection abort handled safely");

  // Test 3d: Network failure handling
  let networkFailedHandled = false;
  try {
    // Port 65530 is closed/refused locally
    await request("http://127.0.0.1:65530/api/health", { timeout: 1000 });
  } catch (err) {
    networkFailedHandled = err instanceof ApiError && (err.status === 0 || err.status === 408);
  }
  recordTest("fe_client_network_down_error", networkFailedHandled, "Refused connection wrapped in ApiError");

  // 4. Jobs & Skills API Service Logic
  console.log("\n--- 4. Frontend API Service Query Assembly & Match Logic ---");
  const jobsMod = await server.ssrLoadModule("/src/api/jobs.js");
  const { jobsApi } = jobsMod;

  // Test 4a: Job query string builder
  // We can test the parameter assembly logic by calling getJobs with mock data or inspecting parameter formatting
  recordTest(
    "fe_jobs_api_service_structure",
    typeof jobsApi.getJobs === "function" && typeof jobsApi.getJobById === "function",
    { methods: Object.keys(jobsApi) }
  );

  const skillsMod = await server.ssrLoadModule("/src/api/skills.js");
  const { skillsApi } = skillsMod;
  recordTest(
    "fe_skills_api_service_structure",
    typeof skillsApi.getTopSkills === "function" &&
      typeof skillsApi.getSkillsByRole === "function" &&
      typeof skillsApi.getEmergingSkills === "function",
    { methods: Object.keys(skillsApi) }
  );

  const salaryMod = await server.ssrLoadModule("/src/api/salary.js");
  const { salaryApi } = salaryMod;
  recordTest(
    "fe_salary_api_service_structure",
    typeof salaryApi.predictSalary === "function" && typeof salaryApi.getModelMetadata === "function",
    { methods: Object.keys(salaryApi) }
  );

  const recMod = await server.ssrLoadModule("/src/api/recommendations.js");
  const { recommendationsApi } = recMod;
  recordTest(
    "fe_recommendations_api_service_structure",
    typeof recommendationsApi.getCareerRecommendations === "function" &&
      typeof recommendationsApi.getSkillGapAnalysis === "function" &&
      typeof recommendationsApi.generateLearningRoadmap === "function" &&
      typeof recommendationsApi.extractResumeSkills === "function" &&
      typeof recommendationsApi.getSupportedRoles === "function",
    { methods: Object.keys(recommendationsApi) }
  );

  // 5. Clean up Vite server
  await server.close();

  // Save Step 7 results
  console.log("\n=======================================================");
  console.log(`STEP 7 VERIFICATION COMPLETE: ${results.summary.passed}/${results.summary.total} PASSED`);
  console.log("=======================================================");

  fs.writeFileSync(
    path.resolve(DOCS_TESTING_DIR, "step7_frontend_results.json"),
    JSON.stringify(results, null, 2),
    "utf-8"
  );
  console.log(`[*] Saved Step 7 JSON report to ${DOCS_TESTING_DIR}/step7_frontend_results.json`);
}

runStep7().catch((err) => {
  console.error("FATAL in runStep7:", err);
  process.exit(1);
});
