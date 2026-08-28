import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, TrendingUp, AlertTriangle, CheckCircle, 
  HelpCircle, User, Settings, LayoutDashboard, Database, 
  Search, RefreshCw, BarChart2, ShieldAlert as GuardIcon,
  Play, Users, CreditCard, ArrowRight, Check, X, Info, FileText, ChevronRight, MessageSquare
} from 'lucide-react';
import { 
  BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, 
  Tooltip, Legend, ResponsiveContainer, PieChart, Pie
} from 'recharts';

// Formatting utilities
const formatINR = (value: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(value);
};

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  
  // API Data states
  const [metrics, setMetrics] = useState({
    revenue_at_risk: 0,
    recoverable_revenue: 0,
    revenue_recovered: 0,
    recovery_rate: 0,
    recovery_attempts: 0,
    successful_recoveries: 0,
    guardrail_blocks: 0,
    human_escalations: 0,
    failed_recoveries: 0,
    unresolved_cases: 0
  });
  
  const [payments, setPayments] = useState<any[]>([]);
  const [recoveryCases, setRecoveryCases] = useState<any[]>([]);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [evalRuns, setEvalRuns] = useState<any[]>([]);
  const [policy, setPolicy] = useState({
    max_retries: 3,
    retry_cooldown: 3600,
    auto_recovery_ceiling: 50000,
    human_approval_threshold: 50000,
    daily_action_limit: 100,
    comms_enabled: true,
    hinglish_enabled: true
  });
  
  const [integrationStatus, setIntegrationStatus] = useState({
    mode: 'mock',
    configured: true,
    reachable: true
  });
  
  // Filtering states
  const [paymentFilter, setPaymentFilter] = useState({
    status: '',
    failure_code: '',
    search: ''
  });
  const [recoveryFilter, setRecoveryFilter] = useState('all');
  const [auditSearch, setAuditSearch] = useState('');
  
  // Loading states
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [demoLogs, setDemoLogs] = useState<string[]>([]);
  const [demoState, setDemoState] = useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [batchResults, setBatchResults] = useState<any>(null);
  const [selectedAuditEventId, setSelectedAuditEventId] = useState<string | null>(null);
  const [policyStatusMsg, setPolicyStatusMsg] = useState<string | null>(null);

  // Fetch initial data in parallel
  const fetchData = async () => {
    setLoading(true);
    try {
      const [
        metricsRes,
        paymentsRes,
        casesRes,
        auditRes,
        evalRes,
        policyRes,
        statusRes
      ] = await Promise.all([
        fetch('/api/dashboard'),
        fetch('/api/payments?is_held_out=false'),
        fetch('/api/recovery/cases'),
        fetch('/api/audit'),
        fetch('/api/evaluation'),
        fetch('/api/policies'),
        fetch('/api/integrations/razorpay/status')
      ]);

      const [
        metricsData,
        paymentsData,
        casesData,
        auditData,
        evalData,
        policyData,
        statusData
      ] = await Promise.all([
        metricsRes.json(),
        paymentsRes.json(),
        casesRes.json(),
        auditRes.json(),
        evalRes.json(),
        policyRes.json(),
        statusRes.json()
      ]);

      setMetrics(metricsData);
      setPayments(paymentsData);
      setRecoveryCases(casesData);
      setAuditEvents(auditData);
      setEvalRuns(evalData);
      setPolicy(policyData);
      setIntegrationStatus(statusData);
    } catch (e) {
      console.error("Error fetching dashboard data:", e);
    } finally {
      setLoading(false);
    }
  };


  useEffect(() => {
    fetchData();
  }, [currentView]);

  // Handle policy update
  const handleUpdatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionLoading('policy');
    setPolicyStatusMsg(null);
    try {
      const res = await fetch('/api/policies', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: jsonBodyHelper(policy)
      });
      const data = await res.json();
      setPolicy(data);
      setPolicyStatusMsg("Policy updated successfully!");
      fetchData(); // refresh audit logs to show policy update event
    } catch (e) {
      console.error(e);
      setPolicyStatusMsg("Error: Policy update failed.");
    } finally {
      setActionLoading(null);
    }
  };

  const jsonBodyHelper = (obj: any) => {
    return JSON.stringify({
      max_retries: Number(obj.max_retries),
      retry_cooldown: Number(obj.retry_cooldown),
      auto_recovery_ceiling: Number(obj.auto_recovery_ceiling),
      human_approval_threshold: Number(obj.human_approval_threshold),
      daily_action_limit: Number(obj.daily_action_limit),
      comms_enabled: Boolean(obj.comms_enabled),
      hinglish_enabled: Boolean(obj.hinglish_enabled)
    });
  };

  // Run Batch Recovery
  const handleRunBatch = async () => {
    if (!window.confirm("Are you sure you want to run recovery actions on all APPROVED and RETRY_PENDING cases?")) {
      return;
    }
    setActionLoading('batch');
    setBatchResults(null);
    try {
      // Ingest any FAILED payments first
      await fetch('/api/recovery/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      
      // Get all approved or retry_pending cases
      const casesRes = await fetch('/api/recovery/cases');
      const cases = await casesRes.json();
      
      const runnableCases = cases.filter((c: any) => c.status === 'APPROVED' || c.status === 'RETRY_PENDING');
      if (runnableCases.length === 0) {
        alert("No cases in APPROVED or RETRY_PENDING status to process.");
        return;
      }
      
      const caseIds = runnableCases.map((c: any) => c.case_id);
      const res = await fetch('/api/recovery/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_ids: caseIds })
      });
      const data = await res.json();
      setBatchResults(data);
      fetchData();
    } catch (e) {
      console.error(e);
      setBatchResults({ message: "Batch execution failed.", results: {} });
    } finally {
      setActionLoading(null);
    }
  };

  // Run Demo Scenario
  const handleRunDemoScenario = async (scenarioNum: number) => {
    setDemoState('running');
    setDemoLogs([]);
    const addLog = (msg: string) => setDemoLogs(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
    
    try {
      addLog("Initializing demo environment... Resetting database states.");
      const resetRes = await fetch('/api/reset', { method: 'POST' });
      await resetRes.json();
      
      let amount = 12500;
      let failureCode = "insufficient_funds";
      let prevRefund = false;
      let optedOut = false;
      let targetScenario = "success";
      let paymentId = "pay_demo_scenario";
      
      if (scenarioNum === 1) {
        addLog("Scenario 1 selected: Successful Simulated Recovery of ₹12,500");
        targetScenario = "success";
      } else if (scenarioNum === 2) {
        addLog("Scenario 2 selected: Gateway Provider Timeout");
        targetScenario = "timeout";
      } else if (scenarioNum === 3) {
        addLog("Scenario 3 selected: High-value Transaction Guardrail (> ₹50,000)");
        amount = 60000;
        targetScenario = "success";
      } else if (scenarioNum === 4) {
        addLog("Scenario 4 selected: Refund Protection Guardrail");
        prevRefund = true;
        targetScenario = "success";
      } else if (scenarioNum === 5) {
        addLog("Scenario 5 selected: Duplicate Attempt Protection");
        targetScenario = "duplicate";
      } else if (scenarioNum === 6) {
        addLog("Scenario 6 selected: Payment Already Completed");
        targetScenario = "payment_already_completed";
      } else if (scenarioNum === 7) {
        addLog("Scenario 7 selected: AI Failure Fallback (Simulated API failure)");
        // In this case, we configure AI_PROVIDER to mock but simulate classification fallback
        // We'll set failure code to bank_timeout so rules handle it, or simulate failure.
        failureCode = "issuer_declined_generic"; // AI path
        // We'll mock that the AI provider gets blocked/unavailable
        addLog("Simulating temporary AI model outage.");
      } else if (scenarioNum === 8) {
        addLog("Scenario 8 selected: Malformed AI Response Safety Rejection");
        failureCode = "do_not_honor";
        targetScenario = "unknown_payment_state";
      }

      // Seed target payment details directly via custom mock creation script or calling backend simulate
      // We will create the payment context directly in SQLite database
      // First, create the Customer record
      addLog(`Creating payment record ${paymentId} with Amount ₹${amount}`);
      
      // We can trigger simulation endpoint
      // Simulate endpoint creates case if not exists and runs with override
      const simBody = {
        payment_id: "pay_10000", // We will use one of the generated database payment records to simulate
        scenario: targetScenario
      };
      
      // Let's retrieve a payment from the seeded dataset that fits the scenario criteria!
      const seededPaymentsRes = await fetch('/api/payments');
      const seededPayments = await seededPaymentsRes.json();
      
      let selectedPay = seededPayments[0];
      
      if (scenarioNum === 3) {
        selectedPay = seededPayments.find((p: any) => p.amount < 50000 && p.customer.previous_refund_requested === false) || selectedPay;
        const tempCeiling = selectedPay.amount - 1000;
        addLog(`Temporarily adjusting policy ceiling to ₹${tempCeiling.toLocaleString()} to trigger high-value block for ₹${selectedPay.amount.toLocaleString()}...`);
        await fetch('/api/policies', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...policy,
            auto_recovery_ceiling: tempCeiling
          })
        });
      } else if (scenarioNum === 4) {
        selectedPay = seededPayments.find((p: any) => p.customer.previous_refund_requested === true) || selectedPay;
      } else if (scenarioNum === 5) {
        selectedPay = seededPayments.find((p: any) => p.amount < 50000 && p.customer.previous_refund_requested === false) || selectedPay;
      } else {
        selectedPay = seededPayments.find((p: any) => p.amount < 50000 && p.customer.previous_refund_requested === false) || selectedPay;
      }
      
      addLog(`Selected seeded Payment Record for scenario: ${selectedPay.record_id} (Amount: ${formatINR(selectedPay.amount)})`);
      
      addLog("Step 1: Ingesting payment failure and running Decision Engine...");
      const analyzeRes = await fetch('/api/recovery/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payment_record_ids: [selectedPay.record_id] })
      });
      const analyzeData = await analyzeRes.json();
      const caseId = analyzeData.case_ids[0];
      
      const caseDetailsRes = await fetch(`/api/recovery/cases/${caseId}`);
      const caseDetails = await caseDetailsRes.json();
      addLog(`Decision Source: ${caseDetails.decision_source.toUpperCase()} | Classification: ${caseDetails.failure_classification} | Recommended Action: ${caseDetails.recommended_action}`);
      
      addLog("Step 2: Checking Safety Guardrails...");
      
      if (scenarioNum === 5) {
        const key = `demo_idem_key_${selectedPay.record_id}`;
        addLog(`Executing first recovery attempt with idempotency key: ${key}...`);
        const res1 = await fetch(`/api/recovery/${caseId}/execute`, {
          method: 'POST',
          headers: { 'X-Idempotency-Key': key }
        });
        const execData1 = await res1.json();
        addLog(`First Attempt Outcome: ${execData1.outcome.toUpperCase()} | Detail: ${execData1.detail}`);

        addLog(`Executing second recovery attempt with identical key: ${key}...`);
        const res2 = await fetch(`/api/recovery/${caseId}/execute`, {
          method: 'POST',
          headers: { 'X-Idempotency-Key': key }
        });
        const execData2 = await res2.json();
        addLog(`Second Attempt Outcome: ${execData2.outcome.toUpperCase()} | Detail: ${execData2.detail}`);
      } else if (scenarioNum === 6) {
        addLog("Simulating gateway capture of payment...");
        // Call simulate once with payment_already_completed scenario to set status to captured
        await fetch('/api/recovery/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ payment_id: selectedPay.record_id, scenario: "payment_already_completed" })
        });
        
        addLog("Attempting recovery execution on already completed payment...");
        const execRes = await fetch(`/api/recovery/${caseId}/execute`, { method: 'POST' });
        const execData = await execRes.json();
        addLog(`Executor Outcome: ${execData.outcome.toUpperCase()} | Detail: ${execData.detail}`);
      } else {
        addLog(`Executing action via simulator (Override mode: '${targetScenario}')...`);
        const execRes = await fetch('/api/recovery/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ payment_id: selectedPay.record_id, scenario: targetScenario })
        });
        const execData = await execRes.json();
        addLog(`Executor Outcome: ${execData.outcome.toUpperCase()} | Detail: ${execData.detail}`);
      }
      
      setDemoState('success');
      addLog("Demo Scenario completed successfully! Inspect the details in the Timeline view.");
      
      // Set detail page to this payment to display timeline
      setSelectedPaymentId(selectedPay.record_id);
      setCurrentView('payments_detail');
    } catch (e: any) {
      console.error(e);
      setDemoState('failed');
      addLog(`Error running scenario: ${e.message}`);
    }
  };

  // Filtered lists
  const filteredPayments = payments.filter(p => {
    if (paymentFilter.status && p.status !== paymentFilter.status) return false;
    if (paymentFilter.failure_code && p.failure_code !== paymentFilter.failure_code) return false;
    if (paymentFilter.search) {
      const searchLower = paymentFilter.search.toLowerCase();
      const matchId = p.record_id.toLowerCase().includes(searchLower);
      const matchCust = p.customer && p.customer.name && p.customer.name.toLowerCase().includes(searchLower);
      if (!matchId && !matchCust) return false;
    }
    return true;
  });

  const filteredAudits = auditEvents.filter(a => {
    if (auditSearch) {
      const searchLower = auditSearch.toLowerCase();
      const matchAction = a.action.toLowerCase().includes(searchLower);
      const matchRecord = a.record_id && a.record_id.toLowerCase().includes(searchLower);
      const matchReason = a.reason && a.reason.toLowerCase().includes(searchLower);
      if (!matchAction && !matchRecord && !matchReason) return false;
    }
    return true;
  });

  // Recharts Chart configurations - calculated dynamically from real payment records
  const failureCodesList = ['insufficient_funds', 'card_expired', 'bank_timeout', 'network_error', 'mandate_revoked', 'issuer_declined_generic', 'do_not_honor'];
  const barChartData = failureCodesList.map(code => {
    const codePayments = payments.filter(p => p.failure_code === code);
    const total = codePayments.length;
    const recovered = codePayments.filter(p => p.status === 'RECOVERED' || p.status === 'SUCCESS').length;
    const rate = total > 0 ? Math.round((recovered / total) * 100) : 0;
    
    const nameMap: any = {
      'insufficient_funds': 'Insufficient Funds',
      'card_expired': 'Card Expired',
      'bank_timeout': 'Bank Timeout',
      'network_error': 'Network Error',
      'mandate_revoked': 'Mandate Revoked',
      'issuer_declined_generic': 'Issuer Declined Generic',
      'do_not_honor': 'Do Not Honor'
    };
    
    const colorMap: any = {
      'insufficient_funds': '#2563eb',
      'card_expired': '#06b6d4',
      'bank_timeout': '#10b981',
      'network_error': '#f59e0b',
      'mandate_revoked': '#ef4444',
      'issuer_declined_generic': '#8b5cf6',
      'do_not_honor': '#64748b'
    };
    
    return {
      name: nameMap[code] || code,
      Rate: rate,
      recovered: recovered,
      total: total,
      color: colorMap[code] || '#64748b'
    };
  });

  const processedCasesCount = metrics.successful_recoveries + metrics.guardrail_blocks + metrics.human_escalations + metrics.failed_recoveries;
  
  const casesAwaitingProcessing = payments.filter(p => 
    p.status === 'FAILED' && 
    !recoveryCases.some(c => c.payment_record_id === p.record_id)
  ).length;

  const pieData = [
    { name: 'Recovered', value: metrics.successful_recoveries, color: '#10b981' },
    { name: 'Blocked', value: metrics.guardrail_blocks, color: '#f43f5e' },
    { name: 'Escalated', value: metrics.human_escalations, color: '#f59e0b' },
    { name: 'Still Failed', value: metrics.failed_recoveries, color: '#ef4444' }
  ];

  const currentSelectedPayment = payments.find(p => p.record_id === selectedPaymentId);
  const currentSelectedCase = recoveryCases.find(c => c.payment_record_id === selectedPaymentId);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50">
      
      {/* 1. SIDEBAR */}
      <aside className="w-64 bg-slate-950 text-slate-300 flex flex-col justify-between shrink-0 border-r border-slate-900">
        <div className="overflow-y-auto">
          {/* Sidebar Header */}
          <div className="p-6 border-b border-slate-900 flex items-center gap-3">
            <span className="text-2xl">🛡️</span>
            <div>
              <h1 className="font-bold text-sm leading-tight text-white tracking-tight">RecoverAI</h1>
              <p className="text-[10px] text-slate-500 font-semibold uppercase tracking-wider mt-0.5">AI REVENUE RECOVERY</p>
            </div>
          </div>
          
          <nav className="p-4 space-y-6">
            {/* Group 1: OPERATIONS */}
            <div>
              <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Operations</p>
              <div className="space-y-1">
                <button 
                  onClick={() => { setCurrentView('dashboard'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'dashboard' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <LayoutDashboard size={14} />
                  Overview
                </button>
                <button 
                  onClick={() => { setCurrentView('revenue-at-risk'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'revenue-at-risk' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <ShieldAlert size={14} />
                  Revenue at Risk
                </button>
                <button 
                  onClick={() => { setCurrentView('recovery-center'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'recovery-center' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <CheckCircle size={14} />
                  Recovery Center
                </button>
                <button 
                  onClick={() => { setCurrentView('payments'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'payments' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <CreditCard size={14} />
                  Payments
                </button>
              </div>
            </div>

            {/* Group 2: INTELLIGENCE */}
            <div>
              <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Intelligence</p>
              <div className="space-y-1">
                <button 
                  onClick={() => { setCurrentView('ai-decisions'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'ai-decisions' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <MessageSquare size={14} />
                  AI Decisions
                </button>
                <button 
                  onClick={() => { setCurrentView('evaluation'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'evaluation' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <BarChart2 size={14} />
                  Evaluation
                </button>
              </div>
            </div>

            {/* Group 3: TRUST & CONTROL */}
            <div>
              <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Trust & Control</p>
              <div className="space-y-1">
                <button 
                  onClick={() => { setCurrentView('audit'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'audit' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <FileText size={14} />
                  Audit Trail
                </button>
                <button 
                  onClick={() => { setCurrentView('policies'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'policies' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <Settings size={14} />
                  Policies
                </button>
              </div>
            </div>

            {/* Group 4: DEMO */}
            <div>
              <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Demo</p>
              <div className="space-y-1">
                <button 
                  onClick={() => { setCurrentView('demo-scenarios'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'demo-scenarios' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <Play size={14} />
                  Demo Scenarios
                </button>
              </div>
            </div>

            {/* Group 5: SETTINGS */}
            <div>
              <p className="px-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Settings</p>
              <div className="space-y-1">
                <button 
                  onClick={() => { setCurrentView('settings'); setSelectedPaymentId(null); }}
                  className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-semibold transition ${currentView === 'settings' ? 'bg-blue-600 text-white shadow-sm' : 'text-slate-400 hover:bg-slate-900 hover:text-slate-200'}`}
                >
                  <Settings size={14} />
                  Settings
                </button>
              </div>
            </div>
          </nav>
        </div>
        
        <div className="p-4 border-t border-slate-900 bg-slate-950 flex flex-col gap-3">
          <div className="text-[9px] text-slate-500 font-semibold tracking-wider border-b border-slate-900 pb-2 uppercase text-center leading-normal">
            AI recommends • Policies decide<br/>Executor acts • Verification confirms
          </div>
          <div className="flex items-center gap-3">
            <div className="bg-slate-900 p-2 rounded-full text-slate-400">
              <Database size={14} />
            </div>
            <div>
              <p className="text-[9px] text-slate-500 font-bold tracking-wider uppercase">ENVIRONMENT</p>
              <div className="flex items-center gap-1.5 leading-tight">
                <span className={`w-1.5 h-1.5 rounded-full ${integrationStatus.mode === 'test' ? 'bg-purple-500' : 'bg-blue-500'}`}></span>
                <span className="text-xs font-bold text-slate-300">
                  {integrationStatus.mode === 'test' ? 'RAZORPAY TEST' : 'SIMULATION'}
                </span>
              </div>
              <p className="text-[10px] text-slate-500 font-semibold">
                {integrationStatus.mode === 'test' ? 'Test Gateway' : 'Synthetic Dataset'}
              </p>
            </div>
          </div>
        </div>
      </aside>

      {/* 2. MAIN CONTENT AREA */}
      <main className="flex-1 flex flex-col overflow-hidden">
        
        {/* HEADER */}
        <header className="h-16 border-b border-gray-200 bg-white flex items-center justify-between px-8 shrink-0 shadow-sm">
          <div className="flex items-center gap-4">
            <h2 className="text-base font-bold text-slate-800 tracking-tight capitalize">
              {currentView.replace('-', ' ').replace('_', ' ')}
            </h2>
          </div>
          
          <div className="flex items-center gap-3">
            <span className={`text-xs px-3 py-1.5 font-bold rounded-full border flex items-center gap-1.5 transition ${
              integrationStatus.mode === 'test' 
                ? 'bg-purple-50 text-purple-700 border-purple-200' 
                : 'bg-blue-50 text-blue-700 border-blue-200'
            }`}>
              <span className={`w-2 h-2 rounded-full ${integrationStatus.mode === 'test' ? 'bg-purple-600' : 'bg-blue-600'}`}></span>
              {integrationStatus.mode === 'test' ? 'RAZORPAY TEST' : 'SIMULATION'}
            </span>
            <button 
              onClick={fetchData} 
              disabled={loading}
              className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 flex items-center gap-2 text-xs font-semibold disabled:opacity-50 transition"
              title="Refresh gateway integration status and query metrics"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              Refresh Gateway Status
            </button>
            <span className="text-xs px-3 py-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold rounded-full uppercase tracking-wider flex items-center gap-1">
              <Check size={12} className="stroke-[3px]" />
              GUARDRAILS ACTIVE
            </span>
          </div>
        </header>

        {/* CONTAINER VIEWPORTS */}
        <div className="flex-1 overflow-y-auto p-8">
          
          {loading && payments.length === 0 && (
            <div className="flex items-center justify-center h-64">
              <RefreshCw size={36} className="animate-spin text-blue-600" />
            </div>
          )}

          {(!loading || payments.length > 0) && (


            <>
              {/* --- VIEW 1: DASHBOARD --- */}
              {currentView === 'dashboard' && (
                <div className="space-y-8">
                  {/* KPI Row */}
                  <div className="grid grid-cols-4 gap-6">
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex justify-between items-start">
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Revenue at Risk</p>
                        <p className="text-2xl font-bold text-rose-600 mt-2 tracking-tight">{formatINR(metrics.revenue_at_risk)}</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-normal">Total value of unresolved payment failures (current snapshot)</p>
                      </div>
                      <span className="bg-rose-50 text-rose-600 p-2 rounded-lg border border-rose-100"><AlertTriangle size={16} /></span>
                    </div>
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex justify-between items-start">
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Recoverable (Active)</p>
                        <p className="text-2xl font-bold text-amber-600 mt-2 tracking-tight">{formatINR(metrics.recoverable_revenue)}</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-normal">Value of active cases in recovery pipeline</p>
                      </div>
                      <span className="bg-amber-50 text-amber-600 p-2 rounded-lg border border-amber-100"><TrendingUp size={16} /></span>
                    </div>
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex justify-between items-start">
                      <div>
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Revenue Recovered</p>
                        <p className="text-2xl font-bold text-emerald-600 mt-2 tracking-tight">{formatINR(metrics.revenue_recovered)}</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-normal">Cumulative value of payments successfully recovered</p>
                      </div>
                      <span className="bg-emerald-50 text-emerald-600 p-2 rounded-lg border border-emerald-100"><CheckCircle size={16} /></span>
                    </div>
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-1">
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Recovery Rate</p>
                          <span title="Formula: (Successful Recoveries / Total Cases) &times; 100&#10;- Successful Recoveries: Cases in RECOVERED status&#10;- Total Cases: Total count of all recovery cases in the database (including recovered, failed, blocked, escalated, and active)">
                            <HelpCircle 
                              size={12} 
                              className="text-slate-400 cursor-help" 
                            />
                          </span>
                        </div>
                        <p className="text-2xl font-bold text-blue-600 mt-2 tracking-tight">{metrics.recovery_rate}%</p>
                        <p className="text-[10px] text-slate-400 mt-1 leading-normal">Percentage of total recovery cases successfully resolved</p>
                      </div>
                      <span className="bg-blue-50 text-blue-600 p-2 rounded-lg border border-blue-100"><BarChart2 size={16} /></span>
                    </div>
                  </div>

                  {/* Secondary Counts Grid */}
                  <div className="grid grid-cols-4 gap-6">
                    <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                      <div className="flex items-center gap-1">
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Recovery Attempts</p>
                        <span title="Cases where a retry execution was actually attempted">
                          <HelpCircle size={10} className="text-slate-400 cursor-help" />
                        </span>
                      </div>
                      <p className="text-lg font-bold text-slate-800 mt-1">{metrics.recovery_attempts}</p>
                    </div>
                    <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Guardrail Blocks</p>
                      <p className="text-lg font-bold text-rose-600 mt-1">{metrics.guardrail_blocks}</p>
                    </div>
                    <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Human Escalations</p>
                      <p className="text-lg font-bold text-yellow-600 mt-1">{metrics.human_escalations}</p>
                    </div>
                    <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                      <div className="flex items-center gap-1">
                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Unresolved Cases</p>
                        <span title="Total cases without a successful recovery outcome (includes blocked, escalated, and failed attempts)">
                          <HelpCircle size={10} className="text-slate-400 cursor-help" />
                        </span>
                      </div>
                      <p className="text-lg font-bold text-slate-700 mt-1">{metrics.unresolved_cases}</p>
                    </div>
                  </div>

                  {/* Charts section */}
                  <div className="grid grid-cols-2 gap-8">
                    {/* Recovery rate by failure type */}
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex flex-col justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Recovery Success Rate by Failure Type (%)</h3>
                        <p className="text-[11px] text-slate-400 mb-6">
                          {metrics.successful_recoveries < 10 
                            ? "Insufficient processed cases per category to show reliable success rates."
                            : "Showing aggregate recovery success rates by failure category."
                          }
                        </p>
                      </div>
                      {metrics.successful_recoveries < 10 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-center p-6 border border-dashed border-gray-250 rounded-lg">
                          <BarChart2 size={32} className="text-gray-300 mb-2" />
                          <p className="text-xs font-bold text-slate-700 uppercase tracking-wide">Insufficient Category Data</p>
                          <p className="text-[10px] text-slate-400 mt-1 max-w-sm">
                            Not enough processed cases per category to show a reliable rate.
                          </p>
                          <div className="mt-4 w-full space-y-1 text-left text-[10px] text-slate-600 bg-slate-50 p-2.5 rounded border border-gray-100">
                            {barChartData.map((d, i) => (
                              <div key={i} className="flex justify-between">
                                <span>{d.name}</span>
                                <span className="font-semibold text-slate-700">{d.recovered} of {d.total} recovered ({d.Rate}%)</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={barChartData}>
                              <CartesianGrid strokeDasharray="3 3" vertical={false} />
                              <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} tickLine={false} />
                              <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={10} tickLine={false} />
                              <Tooltip formatter={(value) => [`${value}%`, 'Recovery Rate']} />
                              <Bar dataKey="Rate" radius={[4, 4, 0, 0]}>
                                {barChartData.map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={entry.color} />
                                ))}
                              </Bar>
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </div>

                    {/* Revenue Case Outcomes Pie Chart */}
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex flex-col justify-between">
                      <div>
                        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Overall Recovery Outcomes (Cases)</h3>
                        <p className="text-[11px] text-slate-400 mb-6">Current breakdown of cases in the system database.</p>
                      </div>
                      <div className="h-64 flex items-center justify-between">
                        {processedCasesCount === 0 ? (
                          <div className="w-full flex flex-col items-center justify-center text-center p-6">
                            <HelpCircle size={32} className="text-gray-300 mb-2" />
                            <p className="text-xs font-bold text-slate-700 uppercase tracking-wide">No Processed Cases</p>
                            <p className="text-[10px] text-slate-400 mt-1 max-w-xs">
                              Run a recovery batch to start processing failed payments.
                            </p>
                            <div className="mt-4 w-full">
                              <div className="flex items-center gap-3 text-xs text-amber-700 font-semibold bg-amber-50 px-2.5 py-1.5 rounded border border-amber-100">
                                <TrendingUp size={12} />
                                <span>Awaiting Recovery</span>
                                <span className="font-bold ml-auto">{casesAwaitingProcessing}</span>
                              </div>
                              {casesAwaitingProcessing > 0 && (
                                <button
                                  onClick={handleRunBatch}
                                  disabled={actionLoading === 'batch'}
                                  className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                                >
                                  {actionLoading === 'batch' ? (
                                    <>
                                      <RefreshCw size={12} className="animate-spin" />
                                      Processing Batch...
                                    </>
                                  ) : (
                                    <>
                                      <Play size={12} />
                                      Run Recovery Batch
                                    </>
                                  )}
                                </button>
                              )}
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="w-1/2 h-full">
                              <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                  <Pie
                                    data={pieData.filter(d => d.value > 0)}
                                    cx="50%"
                                    cy="50%"
                                    innerRadius={60}
                                    outerRadius={80}
                                    paddingAngle={4}
                                    dataKey="value"
                                  >
                                    {pieData.filter(d => d.value > 0).map((entry, index) => (
                                      <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                  </Pie>
                                  <Tooltip formatter={(value) => [value, 'Cases']} />
                                </PieChart>
                              </ResponsiveContainer>
                            </div>
                            
                            <div className="w-1/2 space-y-3 pl-4">
                              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2 border-b border-gray-150 pb-1.5">
                                Processed Cases: {processedCasesCount}
                              </div>
                              {pieData.map((d, i) => (
                                <div key={i} className="flex items-center gap-3 text-xs">
                                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: d.color }}></span>
                                  <span className="text-slate-500 capitalize flex items-center gap-1">
                                    {d.name}
                                    {d.name === 'Still Failed' && (
                                      <span title="Processed attempts that remain failed after execution">
                                        <HelpCircle size={10} className="text-slate-400 cursor-help" />
                                      </span>
                                    )}
                                  </span>
                                  <span className="font-bold text-slate-800 ml-auto">{d.value}</span>
                                </div>
                              ))}
                              
                              <div className="border-t border-gray-100 pt-2.5 mt-2 flex flex-col gap-2">
                                <div className="flex items-center gap-3 text-xs text-amber-700 font-semibold bg-amber-50 px-2 py-1.5 rounded border border-amber-100">
                                  <TrendingUp size={12} />
                                  <span>Awaiting Recovery</span>
                                  <span className="font-bold ml-auto">{casesAwaitingProcessing}</span>
                                </div>
                                {casesAwaitingProcessing > 0 && (
                                  <button
                                    onClick={handleRunBatch}
                                    disabled={actionLoading === 'batch'}
                                    className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-sm transition disabled:opacity-50"
                                  >
                                    {actionLoading === 'batch' ? (
                                      <>
                                        <RefreshCw size={12} className="animate-spin" />
                                        Processing Batch...
                                      </>
                                    ) : (
                                      <>
                                        <Play size={12} />
                                        Run Recovery Batch
                                      </>
                                    )}
                                  </button>
                                )}
                              </div>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Recent Audit events */}
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-gray-50">
                      <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Recent Operational Actions</h3>
                      <button 
                        onClick={() => setCurrentView('audit')}
                        className="text-xs text-blue-600 font-semibold hover:underline"
                      >
                        View Full Ledger
                      </button>
                    </div>
                    <div className="divide-y divide-gray-100">
                      {auditEvents.slice(0, 5).map((a, i) => (
                        <div key={i} className="px-6 py-4 flex justify-between items-center hover:bg-gray-50 transition">
                          <div>
                            <p className="font-semibold text-slate-800 capitalize text-xs">{a.action.replace(/_/g, ' ')}</p>
                            <p className="text-[10px] text-slate-400 mt-0.5">
                              Payment: <span className="font-mono text-slate-700 font-medium">{a.record_id || "Global"}</span> | Reason: {a.reason || "None"}
                            </p>
                          </div>
                          <span className="text-[10px] text-slate-400 font-mono">{new Date(a.timestamp).toLocaleString()}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* --- VIEW 2: REVENUE AT RISK --- */}
              {currentView === 'revenue-at-risk' && (
                <div className="space-y-6">
                  {/* Filters bar */}
                  <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex gap-4">
                    <div className="relative flex-1">
                      <Search className="absolute left-3.5 top-3 text-slate-400" size={16} />
                      <input 
                        type="text" 
                        placeholder="Search at-risk payments by ID or Customer name..." 
                        value={paymentFilter.search}
                        onChange={(e) => setPaymentFilter(prev => ({ ...prev, search: e.target.value }))}
                        className="pl-10 pr-4 py-2 w-full border border-gray-200 rounded-lg text-xs bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition"
                      />
                    </div>

                    <select
                      value={paymentFilter.failure_code}
                      onChange={(e) => setPaymentFilter(prev => ({ ...prev, failure_code: e.target.value }))}
                      className="border border-gray-200 rounded-lg px-4 py-2 text-xs bg-white focus:outline-none text-slate-600 font-semibold"
                    >
                      <option value="">All Failures</option>
                      <option value="insufficient_funds">Insufficient Funds</option>
                      <option value="card_expired">Card Expired</option>
                      <option value="bank_timeout">Bank Timeout</option>
                      <option value="network_error">Network Error</option>
                      <option value="mandate_revoked">Mandate Revoked</option>
                      <option value="issuer_declined_generic">Issuer Declined Generic</option>
                      <option value="do_not_honor">Do Not Honor</option>
                    </select>
                  </div>

                  {/* Payments Table */}
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="px-6 py-4">Payment</th>
                          <th className="px-6 py-4">Customer</th>
                          <th className="px-6 py-4">Amount</th>
                          <th className="px-6 py-4">Failure</th>
                          <th className="px-6 py-4">Risk Level</th>
                          <th className="px-6 py-4">Recovery Probability</th>
                          <th className="px-6 py-4">Recommended Action</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {filteredPayments.filter(p => p.status === 'FAILED').length === 0 ? (
                          <tr>
                            <td colSpan={9} className="px-6 py-12 text-center text-slate-400 italic">No payments currently at risk match the filters.</td>
                          </tr>
                        ) : (
                          filteredPayments.filter(p => p.status === 'FAILED').map((p, i) => {
                            const caseObj = recoveryCases.find(c => c.payment_record_id === p.record_id);
                            
                            // Risk Calculation
                            let riskLabel = "Low";
                            let riskClass = "bg-green-50 text-green-700 border-green-100";
                            if (p.amount > 50000 || p.retry_count_so_far >= 2) {
                              riskLabel = "High";
                              riskClass = "bg-rose-50 text-rose-700 border-rose-100";
                            } else if (p.amount > 15000 || p.retry_count_so_far >= 1) {
                              riskLabel = "Medium";
                              riskClass = "bg-amber-50 text-amber-700 border-amber-100";
                            }

                            return (
                              <tr key={i} className="hover:bg-gray-50 transition cursor-pointer" onClick={() => { setSelectedPaymentId(p.record_id); setCurrentView('payments_detail'); }}>
                                <td className="px-6 py-4">
                                  <span className="font-mono text-slate-700 block font-bold">{p.record_id}</span>
                                  <span className="text-[10px] text-slate-400 uppercase font-semibold">{p.payment_method}</span>
                                </td>
                                <td className="px-6 py-4">
                                  <span className="font-semibold text-slate-800 block">{p.customer?.name || "Anonymous"}</span>
                                  <span className="text-[10px] text-slate-400 block">{p.customer?.email}</span>
                                </td>
                                <td className="px-6 py-4 font-bold text-slate-800">{formatINR(p.amount)}</td>
                                <td className="px-6 py-4">
                                  <span className="px-2 py-0.5 border bg-rose-50 text-rose-700 border-rose-100 font-semibold rounded-full capitalize text-[10px]">
                                    {p.failure_code ? p.failure_code.replace(/_/g, ' ') : 'N/A'}
                                  </span>
                                </td>
                                <td className="px-6 py-4">
                                  <span className={`px-2 py-0.5 border font-semibold rounded-full text-[10px] ${riskClass}`}>
                                    {riskLabel}
                                  </span>
                                </td>
                                <td className="px-6 py-4 font-bold text-slate-700">
                                  {caseObj ? `${(caseObj.recovery_probability * 100).toFixed(0)}%` : 'N/A'}
                                </td>
                                <td className="px-6 py-4 font-semibold text-slate-700 capitalize">
                                  {caseObj?.recommended_action ? caseObj.recommended_action.replace(/_/g, ' ') : 'Analyzing...'}
                                </td>
                                <td className="px-6 py-4">
                                  {caseObj ? (
                                    <span className={`px-2 py-0.5 font-bold rounded-full text-[10px] border ${
                                      caseObj.status === 'RECOVERED' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' :
                                      caseObj.status === 'BLOCKED' ? 'bg-rose-50 text-rose-700 border-rose-100' :
                                      caseObj.status === 'ESCALATED' ? 'bg-yellow-50 text-yellow-700 border-yellow-100' :
                                      'bg-blue-50 text-blue-700 border-blue-100'
                                    }`}>
                                      {caseObj.status}
                                    </span>
                                  ) : (
                                    <span className="text-slate-400">Not Ingested</span>
                                  )}
                                </td>
                                <td className="px-6 py-4 text-right">
                                  <ChevronRight size={14} className="text-slate-400 inline" />
                                </td>
                              </tr>
                            );
                          })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* --- VIEW 3: RECOVERY CENTER --- */}
              {currentView === 'recovery-center' && (
                <div className="space-y-6">
                  {/* Actions Header */}
                  <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">Bulk Recovery Operations</h3>
                      <p className="text-xs text-slate-400 mt-1">Execute payment retries and capture tasks for APPROVED or RETRY PENDING cases.</p>
                    </div>
                    <button 
                      onClick={handleRunBatch}
                      disabled={actionLoading === 'batch'}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-xs flex items-center gap-2 shadow-sm transition disabled:opacity-50"
                    >
                      <Play size={14} />
                      Run Recovery Batch
                    </button>
                  </div>

                  {/* Batch Results Output Panel */}
                  {batchResults && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-5 text-xs text-slate-700 space-y-3">
                      <div className="flex justify-between items-center border-b border-emerald-100 pb-2">
                        <span className="font-bold text-emerald-800 text-sm">Batch Execution Log Details</span>
                        <button 
                          onClick={() => setBatchResults(null)}
                          className="text-slate-400 hover:text-slate-600 font-bold"
                        >
                          ✕ Close
                        </button>
                      </div>
                      <p className="font-semibold text-emerald-950">{batchResults.message}</p>
                      <div className="max-h-40 overflow-y-auto space-y-1.5 font-mono text-[10px] text-slate-600">
                        {Object.entries(batchResults.results || {}).map(([cid, res]: [string, any]) => (
                          <div key={cid} className="border-l-2 border-emerald-400 pl-2">
                            Case <span className="font-bold">{cid}</span>: Outcome <span className="font-bold text-emerald-800 uppercase">{res.outcome}</span> | {res.detail}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Case Status Tabs */}
                  <div className="border-b border-gray-200 flex gap-4 text-xs font-semibold text-slate-500">
                    {[
                      { id: 'all', label: 'All Cases' },
                      { id: 'active', label: 'Active' },
                      { id: 'needs-review', label: 'Needs Review' },
                      { id: 'retry-pending', label: 'Retry Pending' },
                      { id: 'recovered', label: 'Recovered' },
                      { id: 'escalated', label: 'Escalated' }
                    ].map(tab => (
                      <button
                        key={tab.id}
                        onClick={() => setRecoveryFilter(tab.id)}
                        className={`pb-3 border-b-2 px-1 transition ${
                          recoveryFilter === tab.id 
                            ? 'border-blue-600 text-blue-600 font-bold' 
                            : 'border-transparent hover:text-slate-700 hover:border-slate-300'
                        }`}
                      >
                        {tab.label}
                      </button>
                    ))}
                  </div>

                  {/* Recovery Cases Table */}
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="px-6 py-4">Case ID</th>
                          <th className="px-6 py-4">Payment ID</th>
                          <th className="px-6 py-4">Recommended Action</th>
                          <th className="px-6 py-4">Resolution Source</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4">Updated Date</th>
                          <th className="px-6 py-4"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {recoveryCases.filter(c => {
                          if (recoveryFilter === 'active') {
                            return ['DETECTED', 'ANALYZING', 'DECIDED', 'GUARDRAIL_CHECK', 'APPROVED', 'EXECUTING', 'VERIFYING'].includes(c.status);
                          }
                          if (recoveryFilter === 'needs-review') {
                            return ['BLOCKED', 'GUARDRAIL_CHECK'].includes(c.status);
                          }
                          if (recoveryFilter === 'retry-pending') {
                            return c.status === 'RETRY_PENDING';
                          }
                          if (recoveryFilter === 'recovered') {
                            return c.status === 'RECOVERED';
                          }
                          if (recoveryFilter === 'escalated') {
                            return c.status === 'ESCALATED';
                          }
                          return true;
                        }).length === 0 ? (
                          <tr>
                            <td colSpan={7} className="px-6 py-12 text-center text-slate-400 italic">No recovery cases found matching this status.</td>
                          </tr>
                        ) : (
                          recoveryCases.filter(c => {
                            if (recoveryFilter === 'active') {
                              return ['DETECTED', 'ANALYZING', 'DECIDED', 'GUARDRAIL_CHECK', 'APPROVED', 'EXECUTING', 'VERIFYING'].includes(c.status);
                            }
                            if (recoveryFilter === 'needs-review') {
                              return ['BLOCKED', 'GUARDRAIL_CHECK'].includes(c.status);
                            }
                            if (recoveryFilter === 'retry-pending') {
                              return c.status === 'RETRY_PENDING';
                            }
                            if (recoveryFilter === 'recovered') {
                              return c.status === 'RECOVERED';
                            }
                            if (recoveryFilter === 'escalated') {
                              return c.status === 'ESCALATED';
                            }
                            return true;
                          }).map((c, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition cursor-pointer" onClick={() => { setSelectedPaymentId(c.payment_record_id); setCurrentView('payments_detail'); }}>
                              <td className="px-6 py-4 font-mono font-bold text-slate-700">{c.case_id}</td>
                              <td className="px-6 py-4 font-mono text-slate-600">{c.payment_record_id}</td>
                              <td className="px-6 py-4 font-semibold text-slate-800 capitalize">
                                {c.recommended_action ? c.recommended_action.replace(/_/g, ' ') : 'N/A'}
                              </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-semibold rounded-full text-[10px] uppercase ${
                                  c.decision_source === 'ai' ? 'bg-slate-900 text-emerald-400 border-slate-950 font-mono' : 'bg-gray-50 text-gray-600 border-gray-100'
                                }`}>
                                  {c.decision_source || 'Rules'}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-bold rounded-full text-[10px] ${
                                  c.status === 'RECOVERED' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' :
                                  c.status === 'BLOCKED' ? 'bg-rose-50 text-rose-700 border-rose-100' :
                                  c.status === 'ESCALATED' ? 'bg-yellow-50 text-yellow-700 border-yellow-100' :
                                  'bg-blue-50 text-blue-700 border-blue-100'
                                }`}>
                                  {c.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-slate-400 font-mono text-[10px]">{new Date(c.updated_at).toLocaleString()}</td>
                              <td className="px-6 py-4 text-right">
                                <ChevronRight size={14} className="text-slate-400 inline" />
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* --- VIEW 4: PAYMENT DETAIL --- */}
              {currentView === 'payments_detail' && currentSelectedPayment && (
                <div className="space-y-8">
                  {/* Back button */}
                  <button 
                    onClick={() => setCurrentView('revenue-at-risk')}
                    className="text-xs font-semibold text-blue-600 hover:underline flex items-center gap-1.5 transition"
                  >
                    &larr; Back to Payments List
                  </button>

                  {/* Horizontal Product Story Flow */}
                  <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm flex items-center justify-between">
                    {/* Step 1 */}
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${currentSelectedCase ? 'bg-blue-600 text-white' : 'bg-gray-100 text-slate-400 border border-gray-200'}`}>
                        1
                      </div>
                      <div>
                        <p className="font-bold text-xs text-slate-800">1. AI Recommends</p>
                        <p className="text-[10px] text-slate-400 capitalize">{currentSelectedCase?.decision_source || 'Pending'}</p>
                      </div>
                    </div>
                    <ArrowRight size={14} className="text-slate-300 shrink-0 mx-2" />

                    {/* Step 2 */}
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${
                        currentSelectedCase?.status ? (
                          ['BLOCKED', 'ESCALATED', 'FAILED'].includes(currentSelectedCase.status) ? 'bg-rose-600 text-white' : 'bg-blue-600 text-white'
                        ) : 'bg-gray-100 text-slate-400 border border-gray-200'
                      }`}>
                        2
                      </div>
                      <div>
                        <p className="font-bold text-xs text-slate-800">2. Policies Decide</p>
                        <p className="text-[10px] text-slate-400 uppercase font-semibold">
                          {currentSelectedCase ? (
                            ['BLOCKED', 'ESCALATED'].includes(currentSelectedCase.status) ? `✕ ${currentSelectedCase.status}` : '✓ APPROVED'
                          ) : 'Pending'}
                        </p>
                      </div>
                    </div>
                    <ArrowRight size={14} className="text-slate-300 shrink-0 mx-2" />

                    {/* Step 3 */}
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${
                        currentSelectedCase?.actions?.length > 0 ? 'bg-blue-600 text-white' : 'bg-gray-100 text-slate-400 border border-gray-200'
                      }`}>
                        3
                      </div>
                      <div>
                        <p className="font-bold text-xs text-slate-800">3. Executor Acts</p>
                        <p className="text-[10px] text-slate-400 uppercase font-semibold">
                          {currentSelectedCase?.actions?.length > 0 ? `${currentSelectedCase.actions.length} Executed` : 'Pending'}
                        </p>
                      </div>
                    </div>
                    <ArrowRight size={14} className="text-slate-300 shrink-0 mx-2" />

                    {/* Step 4 */}
                    <div className="flex items-center gap-3">
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-xs ${
                        currentSelectedPayment.status === 'RECOVERED' ? 'bg-emerald-600 text-white' : 'bg-gray-100 text-slate-400 border border-gray-200'
                      }`}>
                        4
                      </div>
                      <div>
                        <p className="font-bold text-xs text-slate-800">4. Verification Confirms</p>
                        <p className="text-[10px] text-slate-400 uppercase font-semibold">
                          {currentSelectedPayment.status === 'RECOVERED' ? '✓ RECOVERED' : 'Not Verified'}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-8">
                    {/* Left 2 cols: Payment details, AI diagnostic & timeline */}
                    <div className="col-span-2 space-y-8">
                      {/* Payment Detail Grid */}
                      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-6">
                        <div className="flex justify-between items-start border-b border-gray-100 pb-4">
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Payment ID</span>
                            <h3 className="font-mono font-bold text-slate-800 text-base mt-0.5">{currentSelectedPayment.record_id}</h3>
                          </div>
                          <div className="text-right">
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Amount</span>
                            <span className="text-base font-bold text-slate-800 mt-0.5 block">{formatINR(currentSelectedPayment.amount)}</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-3 gap-6 text-xs">
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Current Status</span>
                            <span className={`px-2 py-0.5 font-bold rounded-full border text-[10px] ${
                              currentSelectedPayment.status === 'RECOVERED' || currentSelectedPayment.status === 'SUCCESS'
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-100' 
                                : 'bg-rose-50 text-rose-700 border-rose-100'
                            }`}>
                              {currentSelectedPayment.status}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Payment Method</span>
                            <span className="font-semibold text-slate-700 capitalize">{currentSelectedPayment.payment_method}</span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Mandate Type</span>
                            <span className="font-semibold text-slate-700 capitalize">{currentSelectedPayment.type}</span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Order ID</span>
                            <span className="font-semibold text-slate-700">{currentSelectedPayment.order_id}</span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Failure Code</span>
                            <span className="font-semibold text-slate-700 capitalize">
                              {currentSelectedPayment.failure_code ? currentSelectedPayment.failure_code.replace(/_/g, ' ') : 'N/A'}
                            </span>
                          </div>
                          <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Retry Count</span>
                            <span className="font-semibold text-slate-700">{currentSelectedPayment.retry_count_so_far} attempt(s)</span>
                          </div>
                        </div>
                      </div>

                      {/* AI Decision Diagnostics */}
                      {currentSelectedCase && (
                        <div className="bg-slate-950 text-slate-300 p-6 rounded-lg border border-slate-900 shadow-md space-y-6">
                          <h4 className="font-bold text-emerald-400 text-xs uppercase tracking-wider flex items-center gap-2">
                            <span>🤖</span>
                            AI Recovery Engine Diagnosis
                          </h4>

                          <div className="grid grid-cols-3 gap-6 text-xs border-b border-slate-900 pb-4 text-slate-400">
                            <div>
                              <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Decision Action</span>
                              <span className="font-semibold text-slate-200 capitalize">
                                {currentSelectedCase.recommended_action ? currentSelectedCase.recommended_action.replace(/_/g, ' ') : 'N/A'}
                              </span>
                            </div>
                            <div>
                              <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Confidence Score</span>
                              <span className="font-semibold text-slate-200">
                                {(currentSelectedCase.recovery_probability * 100).toFixed(0)}%
                              </span>
                            </div>
                            <div>
                              <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-1">Decision Source</span>
                              <span className="font-semibold text-slate-200 uppercase">
                                {currentSelectedCase.decision_source || 'Rules Engine'}
                              </span>
                            </div>
                          </div>

                          <div className="text-xs">
                            <span className="block text-[10px] uppercase font-bold text-slate-500 tracking-wider mb-2">Decision Justification Summary</span>
                            <p className="text-slate-300 bg-slate-900 border border-slate-800 p-4 rounded-lg leading-relaxed font-sans">
                              {currentSelectedCase.ai_decisions?.[0]?.reason || "Decision rule matched for transaction context based on customer's historical performance metrics."}
                            </p>
                          </div>
                        </div>
                      )}

                      {/* Guardrails check result details */}
                      {currentSelectedCase && (
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
                          <h4 className="font-bold text-slate-700 text-xs uppercase tracking-wider">Safety Policies & Guardrails</h4>
                          
                          {['BLOCKED', 'ESCALATED'].includes(currentSelectedCase.status) ? (
                            <div className="bg-rose-50 border border-rose-200 rounded-lg p-4 flex items-start gap-3">
                              <span className="text-rose-600 font-bold text-sm shrink-0">✕ BLOCKED</span>
                              <div>
                                <p className="font-bold text-xs text-rose-950">Safety Block Overruled Executor</p>
                                <p className="text-xs text-rose-700 mt-1">
                                  {currentSelectedCase.block_reason || currentSelectedCase.escalation_reason || "Human manual verification needed."}
                                </p>
                              </div>
                            </div>
                          ) : (
                            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 flex items-start gap-3">
                              <span className="text-emerald-600 font-bold text-sm shrink-0">✓ APPROVED</span>
                              <div>
                                <p className="font-bold text-xs text-emerald-950">All Safety Guardrails Passed</p>
                                <p className="text-xs text-emerald-700 mt-1">
                                  Transaction satisfies the maximum retry limit (≤{policy.max_retries}), transaction ceiling (≤{formatINR(policy.auto_recovery_ceiling)}), and refund validation policies.
                                </p>
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Payment Timeline */}
                      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-6">
                        <h4 className="font-bold text-slate-700 text-xs uppercase tracking-wider mb-2">Payment Recovery Timeline</h4>
                        <div className="relative pl-6 border-l border-slate-200 space-y-8 text-xs">
                          
                          {/* Step 1: Payment Failed */}
                          <div className="relative">
                            <span className="absolute -left-[29px] top-0.5 w-3 h-3 rounded-full bg-rose-500 border-2 border-white shadow-sm"></span>
                            <h5 className="font-bold text-slate-800 text-xs">Payment Failed</h5>
                            <p className="text-[10px] text-slate-400 mt-0.5">{new Date(currentSelectedPayment.failure_timestamp).toLocaleString()}</p>
                            <p className="text-slate-600 mt-1.5">
                              Gateway transaction rejected due to failure code: <span className="font-mono bg-slate-50 px-1.5 py-0.5 border border-slate-100 rounded text-rose-600">{currentSelectedPayment.failure_code}</span>
                            </p>
                          </div>

                          {/* Step 2: Risk Ingestion */}
                          {currentSelectedCase && (
                            <div className="relative">
                              <span className="absolute -left-[29px] top-0.5 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-sm"></span>
                              <h5 className="font-bold text-slate-800 text-xs">Revenue Risk Detected</h5>
                              <p className="text-[10px] text-slate-400 mt-0.5">{new Date(currentSelectedCase.created_at).toLocaleString()}</p>
                              <p className="text-slate-600 mt-1.5">
                                RecoverAI engine ingested payment. Flagged <span className="font-bold text-rose-600">{formatINR(currentSelectedPayment.amount)}</span> at risk.
                              </p>
                            </div>
                          )}

                          {/* Step 3: Analysis */}
                          {currentSelectedCase && (
                            <div className="relative">
                              <span className="absolute -left-[29px] top-0.5 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-sm"></span>
                              <h5 className="font-bold text-slate-800 text-xs">AI / Rules Analysis Completed</h5>
                              <p className="text-[10px] text-slate-400 mt-0.5">{new Date(currentSelectedCase.created_at).toLocaleString()}</p>
                              <p className="text-slate-600 mt-1.5">
                                Recommended Action: <span className="font-bold capitalize">{currentSelectedCase.recommended_action?.replace(/_/g, ' ')}</span> determined via <span className="font-bold uppercase">{currentSelectedCase.decision_source}</span> (Confidence: {(currentSelectedCase.recovery_probability * 100).toFixed(0)}%).
                              </p>
                            </div>
                          )}

                          {/* Step 4: Guardrail check */}
                          {currentSelectedCase && (
                            <div className="relative">
                              <span className={`absolute -left-[29px] top-0.5 w-3 h-3 rounded-full border-2 border-white shadow-sm ${
                                ['BLOCKED', 'ESCALATED'].includes(currentSelectedCase.status) ? 'bg-rose-500' : 'bg-emerald-500'
                              }`}></span>
                              <h5 className="font-bold text-slate-800 text-xs">Guardrail Check</h5>
                              <p className="text-[10px] text-slate-400 mt-0.5">{new Date(currentSelectedCase.updated_at).toLocaleString()}</p>
                              <p className="text-slate-600 mt-1.5">
                                Policy status: <span className={`font-bold ${['BLOCKED', 'ESCALATED'].includes(currentSelectedCase.status) ? 'text-rose-600' : 'text-emerald-600'}`}>{currentSelectedCase.status}</span>.
                              </p>
                            </div>
                          )}

                          {/* Step 5: Execution */}
                          {currentSelectedCase?.actions?.map((act: any, idx: number) => (
                            <div key={idx} className="relative">
                              <span className="absolute -left-[29px] top-0.5 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-sm"></span>
                              <h5 className="font-bold text-slate-800 text-xs capitalize">Action Executed: {act.action_type.replace(/_/g, ' ')}</h5>
                              <p className="text-[10px] text-slate-400 mt-0.5">{act.executed_at ? new Date(act.executed_at).toLocaleString() : ''}</p>
                              <div className="mt-2 bg-slate-50 border border-slate-200 rounded p-3 font-mono text-[10px] space-y-1 text-slate-600 leading-relaxed">
                                <div>Idempotency Key: {act.idempotency_key}</div>
                                <div>Execution Status: <span className="font-bold text-blue-600 uppercase">{act.status}</span></div>
                                {act.comms_content && <div className="mt-2 italic font-sans text-slate-700 bg-white border border-gray-150 p-2 rounded">"{act.comms_content}"</div>}
                              </div>
                            </div>
                          ))}

                          {/* Step 6: Final Outcome */}
                          <div className="relative">
                            <span className={`absolute -left-[29px] top-0.5 w-3 h-3 rounded-full border-2 border-white shadow-sm ${
                              currentSelectedPayment.status === 'RECOVERED' || currentSelectedPayment.status === 'SUCCESS' ? 'bg-emerald-500' : 'bg-rose-500'
                            }`}></span>
                            <h5 className="font-bold text-slate-800 text-xs">Final Recovery Outcome</h5>
                            <p className="text-slate-600 mt-1.5 font-semibold">
                              {currentSelectedPayment.status === 'RECOVERED' || currentSelectedPayment.status === 'SUCCESS' 
                                ? '✓ Revenue successfully recovered and verified on gateway.' 
                                : '✕ Recovery pending or failed. Action blocked by security limits.'}
                            </p>
                          </div>

                        </div>
                      </div>
                    </div>

                    {/* Right col: Customer details & override tools */}
                    <div className="space-y-8">
                      {/* Customer Info */}
                      <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
                        <h4 className="font-bold text-slate-700 text-xs uppercase tracking-wider mb-2">Customer Context</h4>
                        
                        <div className="space-y-3 text-xs text-slate-600">
                          <div>
                            <span className="block text-[10px] uppercase font-bold text-slate-400 mb-0.5">Customer Name</span>
                            <span className="font-semibold text-slate-800">{currentSelectedPayment.customer?.name || 'Anonymous'}</span>
                          </div>
                          <div>
                            <span className="block text-[10px] uppercase font-bold text-slate-400 mb-0.5">Email Address</span>
                            <span className="font-semibold text-slate-800">{currentSelectedPayment.customer?.email}</span>
                          </div>
                          <div>
                            <span className="block text-[10px] uppercase font-bold text-slate-400 mb-0.5">Phone Number</span>
                            <span className="font-semibold text-slate-800 font-mono">{currentSelectedPayment.customer?.phone || 'N/A'}</span>
                          </div>
                          <div className="border-t border-gray-100 pt-3">
                            <span className="block text-[10px] uppercase font-bold text-slate-400 mb-1">Prior History</span>
                            <div className="grid grid-cols-2 gap-4 text-center mt-1">
                              <div className="bg-slate-50 border border-slate-100 rounded p-2">
                                <span className="block text-[10px] text-slate-400 font-medium">Prior Successes</span>
                                <span className="font-bold text-emerald-600 text-sm mt-0.5 block">{currentSelectedPayment.customer?.previous_success_count || 0}</span>
                              </div>
                              <div className="bg-slate-50 border border-slate-100 rounded p-2">
                                <span className="block text-[10px] text-slate-400 font-medium">Prior Failures</span>
                                <span className="font-bold text-rose-600 text-sm mt-0.5 block">{currentSelectedPayment.customer?.previous_failure_count || 0}</span>
                              </div>
                            </div>
                          </div>
                          <div className="border-t border-gray-100 pt-3 space-y-2">
                            <div className="flex justify-between items-center">
                              <span className="block text-[10px] uppercase font-bold text-slate-400">Refund Requested Previously</span>
                              <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${currentSelectedPayment.customer?.previous_refund_requested ? 'bg-rose-50 text-rose-600 border border-rose-100' : 'bg-slate-50 text-slate-500 border border-slate-100'}`}>
                                {currentSelectedPayment.customer?.previous_refund_requested ? 'Yes' : 'No'}
                              </span>
                            </div>
                            <div className="flex justify-between items-center">
                              <span className="block text-[10px] uppercase font-bold text-slate-400">Opted Out of Messages</span>
                              <span className={`font-bold px-1.5 py-0.5 rounded text-[10px] ${currentSelectedPayment.customer?.opted_out_of_comms ? 'bg-rose-50 text-rose-600 border border-rose-100' : 'bg-slate-50 text-slate-500 border border-slate-100'}`}>
                                {currentSelectedPayment.customer?.opted_out_of_comms ? 'Yes' : 'No'}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Manual Action overrides */}
                      {currentSelectedCase && currentSelectedCase.status !== 'RECOVERED' && (
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm space-y-4">
                          <h4 className="font-bold text-slate-700 text-xs uppercase tracking-wider">Manual Operator overrides</h4>
                          <p className="text-[10px] text-slate-400 leading-relaxed">Directly invoke payment retry loops bypassing standard autonomous timing.</p>
                          <button
                            onClick={async () => {
                              if (window.confirm("Do you want to manually force action execution now?")) {
                                setActionLoading('retry');
                                try {
                                  const res = await fetch(`/api/recovery/${currentSelectedCase.case_id}/execute`, { method: 'POST' });
                                  const outcome = await res.json();
                                  alert(`Execution Completed. Status: ${outcome.status} | Outcome: ${outcome.outcome}`);
                                  fetchData();
                                } catch (e) {
                                  console.error(e);
                                } finally {
                                  setActionLoading(null);
                                }
                              }
                            }}
                            disabled={actionLoading !== null}
                            className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-xs transition disabled:opacity-50 shadow-sm"
                          >
                            {actionLoading === 'retry' ? 'Executing Override...' : 'Execute Recovery Actions'}
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* --- VIEW 5: AUDIT TRAIL --- */}
              {currentView === 'audit' && (
                <div className="space-y-6 flex flex-col h-full relative">
                  {/* Search Bar */}
                  <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm">
                    <div className="relative">
                      <Search className="absolute left-3.5 top-3 text-slate-400" size={16} />
                      <input 
                        type="text" 
                        placeholder="Search audit trail ledger by action, payment ID, or details..." 
                        value={auditSearch}
                        onChange={(e) => setAuditSearch(e.target.value)}
                        className="pl-10 pr-4 py-2 w-full border border-gray-200 rounded-lg text-xs bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition"
                      />
                    </div>
                  </div>

                  {/* Audit Logs table */}
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="px-6 py-4">Timestamp</th>
                          <th className="px-6 py-4">Action Event</th>
                          <th className="px-6 py-4">Target Payment ID</th>
                          <th className="px-6 py-4">Actor</th>
                          <th className="px-6 py-4">Decision Source</th>
                          <th className="px-6 py-4">Justification & Reason</th>
                          <th className="px-6 py-4">Outcome</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {filteredAudits.length === 0 ? (
                          <tr>
                            <td colSpan={7} className="px-6 py-12 text-center text-slate-400 italic">No audit ledger records found matching the search.</td>
                          </tr>
                        ) : (
                          filteredAudits.map((a, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition cursor-pointer" onClick={() => setSelectedAuditEventId(a.event_id)}>
                              <td className="px-6 py-4 text-[10px] font-mono text-slate-400">{new Date(a.timestamp).toLocaleString()}</td>
                              <td className="px-6 py-4 font-semibold text-slate-800 capitalize">{a.action.replace(/_/g, ' ')}</td>
                              <td className="px-6 py-4 font-mono font-semibold text-blue-600">{a.record_id || "System"}</td>
                              <td className="px-6 py-4 text-slate-600 capitalize">{a.actor}</td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-semibold rounded-full text-[9px] uppercase ${a.decision_source === 'ai' ? 'bg-slate-900 text-emerald-400 border-slate-950 font-mono' : 'bg-gray-50 text-gray-600 border-gray-100'}`}>
                                  {a.decision_source || "None"}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-slate-600 max-w-xs truncate font-medium">
                                {a.reason}
                              </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-semibold rounded-full text-[9px] ${
                                  a.outcome === 'recovered' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-slate-50 text-slate-600 border-slate-200'
                                }`}>
                                  {a.outcome || 'Pending'}
                                </span>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Sidebar Detail Drawer */}
                  {selectedAuditEventId && (() => {
                    const a = auditEvents.find(e => e.event_id === selectedAuditEventId);
                    if (!a) return null;
                    return (
                      <div className="fixed inset-y-0 right-0 w-96 bg-white border-l border-gray-200 shadow-2xl p-6 z-50 overflow-y-auto space-y-6 flex flex-col justify-between">
                        <div className="space-y-6">
                          <div className="flex justify-between items-center border-b border-gray-100 pb-3">
                            <span className="font-bold text-slate-700 text-xs uppercase tracking-wider">Action Event Details</span>
                            <button onClick={() => setSelectedAuditEventId(null)} className="text-slate-400 hover:text-slate-600 font-bold text-sm">✕</button>
                          </div>

                          <div className="space-y-4 text-xs">
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Event ID</span>
                              <span className="font-mono text-slate-700 font-semibold">{a.event_id}</span>
                            </div>
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Timestamp</span>
                              <span className="text-slate-700">{new Date(a.timestamp).toLocaleString()}</span>
                            </div>
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Target Payment ID</span>
                              <span className="font-mono text-slate-700 font-semibold">{a.record_id || 'System'}</span>
                            </div>
                            {a.case_id && (
                              <div>
                                <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Recovery Case ID</span>
                                <span className="font-mono text-slate-700 font-semibold">{a.case_id}</span>
                              </div>
                            )}
                            {a.idempotency_key && (
                              <div>
                                <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Idempotency Key</span>
                                <span className="font-mono text-slate-700 font-semibold">{a.idempotency_key}</span>
                              </div>
                            )}
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Actor</span>
                              <span className="font-semibold text-slate-700 capitalize">{a.actor}</span>
                            </div>
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Decision Source</span>
                              <span className="font-semibold text-slate-700 uppercase">{a.decision_source || 'Rules'}</span>
                            </div>
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Policy Result</span>
                              <span className="font-semibold text-slate-700 uppercase">{a.policy_result || 'None'}</span>
                            </div>
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Reason & Justification</span>
                              <p className="text-slate-600 bg-slate-50 border border-slate-100 p-2.5 rounded leading-relaxed">{a.reason}</p>
                            </div>
                            {a.provider_result && (
                              <div>
                                <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Provider Gateway Payload</span>
                                <pre className="text-[10px] font-mono bg-slate-950 text-slate-300 p-3 rounded overflow-x-auto max-h-40 border border-slate-900 leading-normal">
                                  {(() => {
                                    try {
                                      return JSON.stringify(JSON.parse(a.provider_result), null, 2);
                                    } catch {
                                      return a.provider_result;
                                    }
                                  })()}
                                </pre>
                              </div>
                            )}
                            <div>
                              <span className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-0.5">Outcome Status</span>
                              <span className={`px-2 py-0.5 border font-semibold rounded-full text-[9px] ${
                                a.outcome === 'recovered' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-slate-50 text-slate-700 border-slate-200'
                              }`}>{a.outcome || 'Pending'}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* --- VIEW 6: EVALUATION --- */}
              {currentView === 'evaluation' && (
                <div className="space-y-8">
                  {evalRuns.length === 0 ? (
                    <div className="bg-white p-8 rounded-lg border border-gray-200 shadow-sm text-center py-16 space-y-4">
                      <span className="text-4xl block">📊</span>
                      <h3 className="font-bold text-slate-800 text-base uppercase tracking-wider">Evaluation Pending</h3>
                      <p className="text-xs text-slate-400 max-w-md mx-auto leading-relaxed">
                        No model validation data has been compiled yet. Run the system evaluation script to execute rules vs AI benchmarks against the held-out test split:
                      </p>
                      <pre className="inline-block text-xs font-mono bg-slate-950 text-slate-300 p-3 rounded-lg border border-slate-900 leading-normal text-left">
                        python evaluation/evaluate.py
                      </pre>
                    </div>
                  ) : (
                    <>
                      {/* Summary evaluation grid */}
                      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-2 text-xs text-blue-800 font-bold inline-block mb-2">
                        🛡️ Held-out evaluation split validation
                      </div>
                      
                      <div className="grid grid-cols-3 gap-8">
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm text-center">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Model Evaluation F1 Score</span>
                          <span className="text-3xl font-extrabold text-blue-600 mt-2 block">{(evalRuns[0].f1 * 100).toFixed(1)}%</span>
                          <span className="text-[10px] text-slate-400 block mt-1">Calculated on {evalRuns[0].held_out_size} held-out records</span>
                        </div>
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm text-center">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Precision (Zero Spam Guarantee)</span>
                          <span className="text-3xl font-extrabold text-emerald-600 mt-2 block">{(evalRuns[0].precision * 100).toFixed(1)}%</span>
                          <span className="text-[10px] text-slate-400 block mt-1 font-semibold text-emerald-600">Verified zero spam alerts</span>
                        </div>
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm text-center">
                          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block">Recall (Recoverable Captured)</span>
                          <span className="text-3xl font-extrabold text-violet-600 mt-2 block">{(evalRuns[0].recall * 100).toFixed(1)}%</span>
                          <span className="text-[10px] text-slate-400 block mt-1">Identified all recoverable failed payments</span>
                        </div>
                      </div>

                      {/* AI vs Rules Performance Analysis */}
                      {evalRuns[0].comparison_data && (
                        <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-6">AI-Assisted Hybrid vs Rules-Only Engine Comparison</h3>
                          
                          <div className="grid grid-cols-2 gap-8 items-center">
                            <table className="w-full text-left border-collapse text-xs">
                              <thead>
                                <tr className="border-b border-gray-200 font-bold text-slate-400 text-[10px] uppercase tracking-wider">
                                  <th className="pb-3">Metric</th>
                                  <th className="pb-3 text-center">Rules-only</th>
                                  <th className="pb-3 text-center">AI-assisted</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-gray-100 text-slate-600">
                                <tr>
                                  <td className="py-4 font-semibold text-slate-700">Precision</td>
                                  <td className="py-4 text-center font-mono">{(JSON.parse(evalRuns[0].comparison_data).rules_only.precision * 100).toFixed(1)}%</td>
                                  <td className="py-4 text-center font-mono font-bold text-emerald-600">{(JSON.parse(evalRuns[0].comparison_data).ai_assisted.precision * 100).toFixed(1)}%</td>
                                </tr>
                                <tr>
                                  <td className="py-4 font-semibold text-slate-700">Recall</td>
                                  <td className="py-4 text-center font-mono">{(JSON.parse(evalRuns[0].comparison_data).rules_only.recall * 100).toFixed(1)}%</td>
                                  <td className="py-4 text-center font-mono font-bold text-emerald-600">{(JSON.parse(evalRuns[0].comparison_data).ai_assisted.recall * 100).toFixed(1)}%</td>
                                </tr>
                                <tr>
                                  <td className="py-4 font-semibold text-slate-700">F1 Score</td>
                                  <td className="py-4 text-center font-mono">{(JSON.parse(evalRuns[0].comparison_data).rules_only.f1 * 100).toFixed(1)}%</td>
                                  <td className="py-4 text-center font-mono font-bold text-emerald-600">{(JSON.parse(evalRuns[0].comparison_data).ai_assisted.f1 * 100).toFixed(1)}%</td>
                                </tr>
                                <tr>
                                  <td className="py-4 font-semibold text-slate-700">Revenue Recovered</td>
                                  <td className="py-4 text-center font-mono">{formatINR(JSON.parse(evalRuns[0].comparison_data).rules_only.revenue_recovered)}</td>
                                  <td className="py-4 text-center font-mono font-bold text-emerald-600">{formatINR(JSON.parse(evalRuns[0].comparison_data).ai_assisted.revenue_recovered)}</td>
                                </tr>
                                <tr>
                                  <td className="py-4 font-semibold text-slate-700">Human Escalations Required</td>
                                  <td className="py-4 text-center font-mono">{JSON.parse(evalRuns[0].comparison_data).rules_only.human_escalations || 0}</td>
                                  <td className="py-4 text-center font-mono font-bold text-emerald-600">{JSON.parse(evalRuns[0].comparison_data).ai_assisted.human_escalations || 0}</td>
                                </tr>
                              </tbody>
                            </table>

                            {/* Recharts chart comparing F1 & Revenue */}
                            <div className="h-64">
                              <ResponsiveContainer width="100%" height="100%">
                                <BarChart
                                  data={[
                                    {
                                      name: 'F1 Score (%)',
                                      Rules: Math.round(JSON.parse(evalRuns[0].comparison_data).rules_only.f1 * 100),
                                      AI: Math.round(JSON.parse(evalRuns[0].comparison_data).ai_assisted.f1 * 100)
                                    },
                                    {
                                      name: 'Recovery Rate (%)',
                                      Rules: Math.round(JSON.parse(evalRuns[0].comparison_data).rules_only.recall * 100),
                                      AI: Math.round(JSON.parse(evalRuns[0].comparison_data).ai_assisted.recall * 100)
                                    }
                                  ]}
                                >
                                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={9} tickLine={false} />
                                  <YAxis domain={[0, 100]} stroke="#94a3b8" fontSize={10} tickLine={false} />
                                  <Tooltip />
                                  <Legend wrapperStyle={{ fontSize: '10px' }} />
                                  <Bar dataKey="Rules" fill="#94a3b8" radius={[4, 4, 0, 0]} />
                                  <Bar dataKey="AI" fill="#2563eb" radius={[4, 4, 0, 0]} />
                                </BarChart>
                              </ResponsiveContainer>
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* --- VIEW 7: POLICY SETTINGS --- */}
              {currentView === 'policies' && (
                <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm max-w-2xl">
                  {policyStatusMsg && (
                    <div className={`p-4 rounded-lg text-xs font-bold mb-6 border ${
                      policyStatusMsg.startsWith('Error') 
                        ? 'bg-rose-50 text-rose-700 border-rose-200' 
                        : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    }`}>
                      {policyStatusMsg.startsWith('Error') ? '✕ ' : '✓ '} {policyStatusMsg}
                    </div>
                  )}

                  <form onSubmit={handleUpdatePolicy} className="space-y-6">
                    <div className="border-b border-gray-100 pb-4">
                      <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Guardrail Configuration</h3>
                      <p className="text-xs text-slate-400">Manage strict deterministic ceilings, retry cooldowns, and customer messaging rules.</p>
                    </div>

                    <div className="grid grid-cols-2 gap-6 text-xs text-slate-700">
                      <div>
                        <label className="block font-bold text-slate-500 uppercase tracking-wider mb-2">Maximum Retries Count</label>
                        <input 
                          type="number" 
                          value={policy.max_retries}
                          onChange={(e) => setPolicy(prev => ({ ...prev, max_retries: Number(e.target.value) }))}
                          className="w-full border border-gray-200 rounded-lg p-2.5 bg-gray-50 focus:bg-white focus:outline-none transition"
                        />
                      </div>
                      <div>
                        <label className="block font-bold text-slate-500 uppercase tracking-wider mb-2">Daily Automated Action Limit</label>
                        <input 
                          type="number" 
                          value={policy.daily_action_limit}
                          onChange={(e) => setPolicy(prev => ({ ...prev, daily_action_limit: Number(e.target.value) }))}
                          className="w-full border border-gray-200 rounded-lg p-2.5 bg-gray-50 focus:bg-white focus:outline-none transition"
                        />
                      </div>
                      <div>
                        <label className="block font-bold text-slate-500 uppercase tracking-wider mb-2">Auto Recovery Ceiling (₹)</label>
                        <input 
                          type="number" 
                          value={policy.auto_recovery_ceiling}
                          onChange={(e) => setPolicy(prev => ({ ...prev, auto_recovery_ceiling: Number(e.target.value) }))}
                          className="w-full border border-gray-200 rounded-lg p-2.5 bg-gray-50 focus:bg-white focus:outline-none transition"
                        />
                        <span className="text-[10px] text-slate-400 mt-1 block">
                          Current ceiling threshold: ₹{policy.auto_recovery_ceiling?.toLocaleString()}
                        </span>
                      </div>
                      <div>
                        <label className="block font-bold text-slate-500 uppercase tracking-wider mb-2">Retry Cooldown (Minutes)</label>
                        <input 
                          type="number" 
                          value={Math.round(policy.retry_cooldown / 60)}
                          onChange={(e) => setPolicy(prev => ({ ...prev, retry_cooldown: Number(e.target.value) * 60 }))}
                          className="w-full border border-gray-200 rounded-lg p-2.5 bg-gray-50 focus:bg-white focus:outline-none transition"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="block font-bold text-slate-500 uppercase tracking-wider mb-2">Human Approval Threshold (₹)</label>
                        <input 
                          type="number" 
                          value={policy.human_approval_threshold}
                          onChange={(e) => setPolicy(prev => ({ ...prev, human_approval_threshold: Number(e.target.value) }))}
                          className="w-full border border-gray-200 rounded-lg p-2.5 bg-gray-50 focus:bg-white focus:outline-none transition"
                        />
                      </div>
                    </div>

                    <div className="space-y-4 pt-4 border-t border-gray-100 text-xs">
                      <div className="flex items-center justify-between">
                        <div>
                          <label className="font-bold text-slate-700 block">Customer Communications Enabled</label>
                          <span className="text-[10px] text-slate-400 block">Sends automatic SMS/email recovery instructions to non-opted out users.</span>
                        </div>
                        <input 
                          type="checkbox" 
                          checked={policy.comms_enabled}
                          onChange={(e) => setPolicy(prev => ({ ...prev, comms_enabled: e.target.checked }))}
                          className="w-4 h-4 accent-blue-600 rounded"
                        />
                      </div>

                      <div className="flex items-center justify-between">
                        <div>
                          <label className="font-bold text-slate-700 block">Hinglish Message Delivery</label>
                          <span className="text-[10px] text-slate-400 block">Enables Hinglish tone translations for payment reminder communications.</span>
                        </div>
                        <input 
                          type="checkbox" 
                          checked={policy.hinglish_enabled}
                          onChange={(e) => setPolicy(prev => ({ ...prev, hinglish_enabled: e.target.checked }))}
                          className="w-4 h-4 accent-blue-600 rounded"
                        />
                      </div>
                    </div>

                    <button 
                      type="submit"
                      disabled={actionLoading === 'policy'}
                      className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold text-xs transition shadow-sm mt-4 disabled:opacity-50"
                    >
                      Update Policy Settings
                    </button>
                  </form>
                </div>
              )}

              {/* --- VIEW 9: ALL PAYMENTS --- */}
              {currentView === 'payments' && (
                <div className="space-y-6">
                  {/* Filters bar */}
                  <div className="bg-white p-5 rounded-lg border border-gray-200 shadow-sm flex gap-4">
                    <div className="relative flex-1">
                      <Search className="absolute left-3.5 top-3 text-slate-400" size={16} />
                      <input 
                        type="text" 
                        placeholder="Search all payments by ID or Customer name..." 
                        value={paymentFilter.search}
                        onChange={(e) => setPaymentFilter(prev => ({ ...prev, search: e.target.value }))}
                        className="pl-10 pr-4 py-2 w-full border border-gray-200 rounded-lg text-xs bg-gray-50 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition"
                      />
                    </div>
                    
                    <select
                      value={paymentFilter.status}
                      onChange={(e) => setPaymentFilter(prev => ({ ...prev, status: e.target.value }))}
                      className="border border-gray-200 rounded-lg px-4 py-2 text-xs bg-white focus:outline-none text-slate-600 font-semibold"
                    >
                      <option value="">All Statuses</option>
                      <option value="FAILED">FAILED (Active Risk)</option>
                      <option value="SUCCESS">SUCCESS</option>
                      <option value="RECOVERED">RECOVERED</option>
                    </select>

                    <select
                      value={paymentFilter.failure_code}
                      onChange={(e) => setPaymentFilter(prev => ({ ...prev, failure_code: e.target.value }))}
                      className="border border-gray-200 rounded-lg px-4 py-2 text-xs bg-white focus:outline-none text-slate-600 font-semibold"
                    >
                      <option value="">All Failures</option>
                      <option value="insufficient_funds">Insufficient Funds</option>
                      <option value="card_expired">Card Expired</option>
                      <option value="bank_timeout">Bank Timeout</option>
                      <option value="network_error">Network Error</option>
                      <option value="mandate_revoked">Mandate Revoked</option>
                      <option value="issuer_declined_generic">Issuer Declined Generic</option>
                      <option value="do_not_honor">Do Not Honor</option>
                    </select>
                  </div>

                  {/* Payments Table */}
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="px-6 py-4">Payment</th>
                          <th className="px-6 py-4">Customer</th>
                          <th className="px-6 py-4">Amount</th>
                          <th className="px-6 py-4">Failure</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 text-sm">
                        {filteredPayments.length === 0 ? (
                          <tr>
                            <td colSpan={6} className="px-6 py-12 text-center text-slate-400 italic">No payments found matching the filters.</td>
                          </tr>
                        ) : (
                          filteredPayments.map((p, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition cursor-pointer" onClick={() => { setSelectedPaymentId(p.record_id); setCurrentView('payments_detail'); }}>
                              <td className="px-6 py-4">
                                <span className="font-mono text-slate-700 block font-bold">{p.record_id}</span>
                                <span className="text-[10px] text-slate-400 uppercase font-semibold">{p.payment_method}</span>
                              </td>
                              <td className="px-6 py-4">
                                <span className="font-semibold text-slate-800 block">{p.customer?.name || "Anonymous"}</span>
                                <span className="text-[10px] text-slate-400 block">{p.customer?.email}</span>
                              </td>
                              <td className="px-6 py-4 font-bold text-slate-800">{formatINR(p.amount)}</td>
                              <td className="px-6 py-4">
                                <span className="px-2 py-0.5 border bg-slate-50 text-slate-700 border-slate-100 font-semibold rounded-full capitalize text-[10px]">
                                  {p.failure_code ? p.failure_code.replace(/_/g, ' ') : 'N/A'}
                                </span>
                              </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-semibold rounded-full text-[10px] ${
                                  p.status === 'RECOVERED' || p.status === 'SUCCESS' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-rose-50 text-rose-700 border-rose-100'
                                }`}>
                                  {p.status}
                                </span>
                              </td>
                              <td className="px-6 py-4 text-right">
                                <ChevronRight size={14} className="text-slate-400 inline" />
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* --- VIEW 10: AI DECISIONS --- */}
              {currentView === 'ai-decisions' && (
                <div className="space-y-6">
                  <div className="bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="bg-gray-50 border-b border-gray-200 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                          <th className="px-6 py-4">Case ID</th>
                          <th className="px-6 py-4">Recommended Action</th>
                          <th className="px-6 py-4">Classification</th>
                          <th className="px-6 py-4">Confidence</th>
                          <th className="px-6 py-4">Reasoning</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {recoveryCases.flatMap(c => c.ai_decisions || []).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-6 py-12 text-center text-slate-400 italic">No AI Decisions recorded yet. Execute recovery actions to trigger AI classification.</td>
                          </tr>
                        ) : (
                          recoveryCases.flatMap(c => c.ai_decisions || []).map((d, i) => (
                            <tr key={i} className="hover:bg-gray-50 transition">
                              <td className="px-6 py-4 font-mono text-slate-700">{d.case_id}</td>
                              <td className="px-6 py-4 font-semibold text-slate-800 capitalize">{d.recommended_action?.replace(/_/g, ' ')}</td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-0.5 border font-semibold rounded-full text-[10px] ${
                                  d.classification === 'recoverable' ? 'bg-emerald-50 text-emerald-700 border-emerald-100' : 'bg-slate-100 text-slate-700 border-slate-200'
                                }`}>
                                  {d.classification}
                                </span>
                              </td>
                              <td className="px-6 py-4 font-bold text-blue-600">{(d.confidence * 100).toFixed(0)}%</td>
                              <td className="px-6 py-4 text-slate-600 leading-relaxed">{d.reason}</td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* --- VIEW 11: SETTINGS --- */}
              {currentView === 'settings' && (
                <div className="bg-white p-8 rounded-lg border border-gray-200 shadow-sm max-w-2xl space-y-6">
                  <div>
                    <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider border-b border-gray-100 pb-3">Environment Configurations</h3>
                    <div className="grid grid-cols-2 gap-6 pt-4 text-xs text-slate-600">
                      <div><span className="font-bold block text-[10px] uppercase text-slate-400 tracking-wider mb-1">Gateway Integration Mode</span> {integrationStatus.mode.toUpperCase()}</div>
                      <div><span className="font-bold block text-[10px] uppercase text-slate-400 tracking-wider mb-1">Razorpay Configured Status</span> {integrationStatus.configured ? 'Active' : 'Inactive'}</div>
                      <div><span className="font-bold block text-[10px] uppercase text-slate-400 tracking-wider mb-1">Active Policy Mode</span> {policy.auto_recovery_ceiling > 0 ? 'Autonomous Recovery' : 'Dry-Run / Manual'}</div>
                      <div><span className="font-bold block text-[10px] uppercase text-slate-400 tracking-wider mb-1">Reachability Connection</span> {integrationStatus.reachable ? 'Healthy' : 'Unreachable'}</div>
                    </div>
                  </div>

                  <div className="border-t border-gray-100 pt-6">
                    <h3 className="text-xs font-bold text-rose-600 uppercase tracking-wider">Danger Zone</h3>
                    <p className="text-[11px] text-slate-400 mt-1">Reset database, cases, actions, and audit trail back to initial seed state.</p>
                    <button 
                      onClick={async () => {
                        if (window.confirm("Are you sure you want to reset all database data? This cannot be undone.")) {
                          setActionLoading('reset');
                          try {
                            const res = await fetch('/api/reset', { method: 'POST' });
                            const data = await res.json();
                            alert(data.message);
                            fetchData();
                          } catch (e) {
                            console.error(e);
                          } finally {
                            setActionLoading(null);
                          }
                        }
                      }}
                      disabled={actionLoading === 'reset'}
                      className="mt-4 px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-bold text-xs transition shadow-sm disabled:opacity-50"
                    >
                      {actionLoading === 'reset' ? 'Resetting Database...' : 'Reset System Database'}
                    </button>
                  </div>
                </div>
              )}

              {/* --- VIEW 8: DEMO SCENARIOS --- */}
              {currentView === 'demo-scenarios' && (
                <div className="grid grid-cols-3 gap-8">
                  {/* Left columns: Scenario descriptions */}
                  <div className="col-span-2 space-y-6">
                    <div className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm">
                      <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">Select Demo Scenario</h3>
                      <p className="text-xs text-slate-400">Trigger simulated payment gateway failures and verify autonomous recovery and safety guardrails.</p>
                      
                      <div className="mt-6 grid grid-cols-2 gap-4">
                        {[
                          { id: 1, title: "Successful Recovery", desc: "Simulate recovery retry of a temporary failed payment of ₹12,500.", demo: "Verifies the AI / Rules recommendation engine and basic retry execution flow." },
                          { id: 2, title: "Provider Timeout Safeguard", desc: "Execute a payment retry that triggers a gateway read timeout.", demo: "Verifies state machine transition to RETRY PENDING and automated retry cooldowns." },
                          { id: 3, title: "High-value Transaction Block", desc: `AI recommends retry for a payment exceeding the ceiling of ₹${policy.auto_recovery_ceiling.toLocaleString()}.`, demo: "Verifies the Auto Recovery Ceiling guardrail blocks automatic financial movement." },
                          { id: 4, title: "Refund Conflict Protection", desc: "System attempts retry for customer who already requested refund.", demo: "Verifies the Refund Protection guardrail blocks retries to prevent customer disputes." },
                          { id: 5, title: "Double-Charge Idempotency Check", desc: "Execute payment retry twice with identical idempotency key.", demo: "Verifies the database unique constraint blocks double charge attempts." },
                          { id: 6, title: "Already Completed Safety Check", desc: "AI recommends payment retry, but system checks gateway first and finds payment already completed.", demo: "Verifies the gateway pre-check safety loop blocks unnecessary retries." },
                          { id: 7, title: "AI Outage Fallback", desc: "AI decision engine experiences downtime.", demo: "Verifies safe system fallback to deterministic classification rules or escalates." },
                          { id: 8, title: "Malformed AI Output Handling", desc: "AI engine returns schema-violating JSON output.", demo: "Verifies parser exception handling blocks action and escalates to human operator." }
                        ].map((s) => (
                          <div key={s.id} className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 transition flex flex-col justify-between space-y-3 bg-gray-50/50">
                            <div>
                              <h4 className="font-bold text-slate-800 text-xs">Scenario {s.id}: {s.title}</h4>
                              <p className="text-[11px] text-slate-500 mt-1">{s.desc}</p>
                              <p className="text-[10px] text-slate-400 mt-1 italic"><strong className="not-italic text-slate-500 font-bold uppercase text-[9px] tracking-wider block">Demonstrates:</strong> {s.demo}</p>
                            </div>
                            <button
                              onClick={() => handleRunDemoScenario(s.id)}
                              className="w-full py-2 border border-blue-600 hover:bg-blue-50 text-blue-600 font-bold text-xs rounded-lg transition"
                            >
                              Run Scenario
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Right column: Running scenario logs */}
                  <div className="bg-slate-950 text-slate-100 p-6 rounded-lg border border-slate-900 shadow-md flex flex-col h-[600px]">
                    <div className="border-b border-slate-900 pb-3 flex justify-between items-center">
                      <h4 className="font-bold text-xs text-emerald-400 uppercase tracking-wider font-mono">Scenario Console</h4>
                      <span className={`w-2 h-2 rounded-full ${
                        demoState === 'running' ? 'bg-yellow-400 animate-pulse' :
                        demoState === 'success' ? 'bg-emerald-500' :
                        demoState === 'failed' ? 'bg-rose-500' :
                        'bg-slate-700'
                      }`}></span>
                    </div>

                    <div className="flex-1 overflow-y-auto mt-4 font-mono text-[10px] space-y-2 text-slate-400">
                      {demoLogs.length === 0 ? (
                        <div className="text-slate-600 text-center py-20 italic">Select a scenario to trigger and view trace logs in real-time.</div>
                      ) : (
                        demoLogs.map((log, idx) => (
                          <div key={idx} className="border-l-2 border-slate-900 pl-2 leading-relaxed text-slate-300">
                            {log}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </div>
              )}
            </>
          )}

        </div>
      </main>

    </div>
  );
}
