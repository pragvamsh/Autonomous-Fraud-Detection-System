import {
    Box, Container, Paper, Typography, Grid, Button, Chip,
    CircularProgress, Dialog, DialogContent, LinearProgress,
    Avatar, IconButton, TextField, Divider, ToggleButton,
    ToggleButtonGroup, Tooltip
} from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import SmartToyIcon from '@mui/icons-material/SmartToy';
import SendIcon from '@mui/icons-material/Send';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import SecurityIcon from '@mui/icons-material/Security';
import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api';
import FlagConfirmationModal from '../components/FlagConfirmationModal';
import BlockNotificationModal from '../components/BlockNotificationModal';

// ── Colour tokens — identical to CustomerDashboard ────────────────────────────
const C = {
    brown: '#7f5539',
    brownMid: '#9c6644',
    brownLight: '#e6ccb2',
    cream: 'rgba(230,204,178,0.15)',
    bg: '#fdf6ef',
    success: '#4caf50',
    error: '#f44336',
    warning: '#ff9800',
    info: '#1976d2',
};

// ── TMA pipeline steps (Stage 1) ────────────────────────────────────────────
const TMA_STEPS = [
    {
        id: 'payment',
        label: 'Payment Processing',
        detail: 'Debiting sender · Crediting recipient · Committing transaction',
        icon: '💳',
        ms: 900,
    },
    {
        id: 'profile',
        label: 'Behaviour Profile Builder',
        detail: 'Analysing 90-day history · Computing avg, std, daily volume',
        icon: '📊',
        ms: 1300,
    },
    {
        id: 'anomaly',
        label: 'Anomaly Signal Extractor',
        detail: 'Z-score · Velocity · Recipient · Time-of-day signals',
        icon: '🔍',
        ms: 1000,
    },
    {
        id: 'ml',
        label: 'ML Layer — Isolation Forest',
        detail: 'Scoring feature vector against learnt behaviour patterns',
        icon: '🧠',
        ms: 800,
    },
    {
        id: 'rag',
        label: 'RAG Knowledge Base',
        detail: 'Retrieving historical cases · Generating context-aware verdict',
        icon: '📚',
        ms: 1800,
    },
    {
        id: 'decision',
        label: 'Decision Engine',
        detail: 'Fusing ML + RAG scores · Applying cold-start penalty',
        icon: '⚖️',
        ms: 600,
    },
    {
        id: 'executor',
        label: 'Response Executor',
        detail: 'Writing fraud alert · Updating transaction record',
        icon: '📝',
        ms: 500,
    },
];

// ── PRA pipeline steps (Stage 2) ─────────────────────────────────────────────
const PRA_STEPS = [
    {
        id: 'pra_temporal',
        label: 'Temporal Analyser',
        detail: 'EWM risk trend · Escalation window · Typology persistence',
        icon: '📈',
        ms: 1200,
    },
    {
        id: 'pra_network',
        label: 'Network Analyser',
        detail: 'Cross-customer fan-out · Recipient risk node scoring',
        icon: '🕸️',
        ms: 1000,
    },
    {
        id: 'pra_rag',
        label: 'Pattern RAG Scorer',
        detail: 'KB adjustment against typologies · Confidence gating',
        icon: '🔗',
        ms: 800,
    },
    {
        id: 'pra_decision',
        label: 'Pattern Decision Engine',
        detail: 'Fusing temporal + network + RAG · Override rule checks',
        icon: '🛡️',
        ms: 600,
    },
];

const RAA_STEPS = [
    { id: 1, label: 'Intelligence Aggregator', detail: 'Fetching alert + pattern data', icon: '📡' },
    { id: 2, label: 'Customer Tier Engine', detail: 'Classifying customer risk tier', icon: '🏅' },
    { id: 3, label: '5-Dimension Scorer', detail: 'Evaluating D1-D5 vectors', icon: '📐' },
    { id: 4, label: 'RAG Context Layer', detail: 'Retrieving typologies & rules', icon: '📚' },
    { id: 5, label: 'Fusion Score Engine', detail: 'Fusing Score_A and RAG context', icon: '⚙️' },
    { id: 6, label: 'Regulatory Checks', detail: 'STR & CTR compliance', icon: '🏛️' },
    { id: 7, label: 'Action Package Dispatch', detail: 'Delegating to ABA', icon: '📨' }
];

// ── ABA pipeline steps (Stage 4 — Alert & Block Agent) ─────────────────────
const ABA_STEPS = [
    { id: 'aba_1', label: 'Package Loader', detail: 'Loading action package from RAA', icon: '📦' },
    { id: 'aba_2', label: 'Gateway Controller', detail: 'Determining payment gateway action', icon: '🚦' },
    { id: 'aba_3', label: 'Action Executor', detail: 'Executing verdict-specific actions', icon: '⚡' },
    { id: 'aba_4', label: 'Notification Engine', detail: 'Queueing customer notifications', icon: '📱' },
    { id: 'aba_5', label: 'Account Controller', detail: 'Handling freeze/credential actions', icon: '🔐' },
    { id: 'aba_6', label: 'Regulatory Router', detail: 'Filing CTR/STR reports', icon: '📋' },
    { id: 'aba_7', label: 'Case Manager', detail: 'Creating fraud cases for CLA', icon: '📁' },
];

// All steps combined for total progress calculation
const ALL_STEPS = [...TMA_STEPS, ...PRA_STEPS];
const TOTAL_STEPS = TMA_STEPS.length + PRA_STEPS.length + RAA_STEPS.length + ABA_STEPS.length;


// Decision display config
const DECISION_CFG = {
    ALLOW: {
        color: C.success,
        bg: `${C.success}12`,
        border: `${C.success}40`,
        emoji: '✅',
        label: 'Transaction Cleared',
        msg: 'No suspicious activity detected. Your payment completed successfully.',
    },
    FLAG: {
        color: C.info,
        bg: `${C.info}12`,
        border: `${C.info}40`,
        emoji: '🚩',
        label: 'Flagged for Review',
        msg: 'Payment sent. Our team will review this transaction shortly.',
    },
    ALERT: {
        color: C.warning,
        bg: `${C.warning}12`,
        border: `${C.warning}40`,
        emoji: '⚠️',
        label: 'High Risk — Alert Triggered',
        msg: 'Payment processed. You have been notified about unusual activity.',
    },
    BLOCK: {
        color: C.error,
        bg: `${C.error}10`,
        border: `${C.error}40`,
        emoji: '🚫',
        label: 'Critical Risk — Blocked',
        msg: 'Transaction reversed. Your account has been restricted pending review.',
    },
};

// ─────────────────────────────────────────────────────────────────────────────
// AnimatedBot
// ─────────────────────────────────────────────────────────────────────────────
function AnimatedBot({ phase, decision }) {
    // phase: 'idle' | 'running' | 'done'
    const dc = decision ? DECISION_CFG[decision] : null;
    const color = dc ? dc.color : C.brown;
    const emoji = phase === 'done' && dc ? dc.emoji : '🤖';

    return (
        <Box sx={{ position: 'relative', width: 96, height: 96, mx: 'auto' }}>
            {/* Outer pulse — only while running */}
            {phase === 'running' && (
                <>
                    <Box sx={{
                        position: 'absolute', inset: -12, borderRadius: '50%',
                        border: `1.5px solid ${C.brownLight}`,
                        animation: 'pulse 1.8s ease-out infinite',
                        '@keyframes pulse': {
                            '0%': { transform: 'scale(0.8)', opacity: 0.9 },
                            '100%': { transform: 'scale(1.4)', opacity: 0 },
                        },
                    }} />
                    <Box sx={{
                        position: 'absolute', inset: -4, borderRadius: '50%',
                        border: `1.5px solid ${C.brownLight}55`,
                        animation: 'pulse 1.8s ease-out 0.5s infinite',
                        '@keyframes pulse': {
                            '0%': { transform: 'scale(0.8)', opacity: 0.9 },
                            '100%': { transform: 'scale(1.4)', opacity: 0 },
                        },
                    }} />
                </>
            )}

            <Avatar sx={{
                width: 96, height: 96,
                bgcolor: `${color}15`,
                border: `3px solid ${color}`,
                fontSize: 44,
                boxShadow: phase === 'running'
                    ? `0 0 24px ${color}50, 0 0 48px ${color}20`
                    : phase === 'done'
                        ? `0 0 16px ${color}40`
                        : 'none',
                transition: 'all 0.5s ease',
                animation: phase === 'running'
                    ? 'float 2s ease-in-out infinite'
                    : phase === 'done'
                        ? 'pop 0.4s cubic-bezier(0.34,1.56,0.64,1)'
                        : 'none',
                '@keyframes float': {
                    '0%,100%': { transform: 'translateY(0px)' },
                    '50%': { transform: 'translateY(-8px)' },
                },
                '@keyframes pop': {
                    '0%': { transform: 'scale(0.7)' },
                    '100%': { transform: 'scale(1)' },
                },
            }}>
                {emoji}
            </Avatar>
        </Box>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// StepRow
// ─────────────────────────────────────────────────────────────────────────────
function StepRow({ step, status }) {
    // status: 'pending' | 'running' | 'done'
    const isRunning = status === 'running';
    const isDone = status === 'done';

    return (
        <Box sx={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1.5,
            py: 1,
            px: 1.5,
            borderRadius: 2,
            bgcolor: isRunning ? `${C.brown}0d`
                : isDone ? `${C.success}09`
                    : 'transparent',
            transition: 'background 0.35s ease',
        }}>
            {/* Status icon col */}
            <Box sx={{ pt: 0.25, minWidth: 22 }}>
                {isDone && (
                    <CheckCircleIcon sx={{
                        color: C.success, fontSize: 20,
                        animation: 'popIn 0.3s cubic-bezier(0.34,1.56,0.64,1)',
                        '@keyframes popIn': {
                            '0%': { transform: 'scale(0)' },
                            '100%': { transform: 'scale(1)' },
                        },
                    }} />
                )}
                {isRunning && (
                    <CircularProgress size={18} thickness={5}
                        sx={{ color: C.brown }} />
                )}
                {status === 'pending' && (
                    <RadioButtonUncheckedIcon sx={{ color: '#d0b898', fontSize: 20 }} />
                )}
            </Box>

            {/* Text col */}
            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography
                    variant="body2"
                    fontWeight={isDone ? 600 : isRunning ? 700 : 500}
                    color={isRunning ? C.brown : isDone ? 'text.primary' : 'text.secondary'}
                    sx={{ transition: 'color 0.3s', fontSize: 13 }}
                >
                    {step.icon}&nbsp; {step.label}
                </Typography>

                {/* Detail line — only while running */}
                {isRunning && (
                    <Typography variant="caption" color="text.secondary"
                        sx={{
                            display: 'block', mt: 0.2,
                            animation: 'fadeIn 0.3s ease',
                            '@keyframes fadeIn': {
                                from: { opacity: 0, transform: 'translateY(4px)' },
                                to: { opacity: 1, transform: 'translateY(0)' },
                            },
                        }}>
                        {step.detail}
                    </Typography>
                )}
            </Box>

            {/* Right badge */}
            <Box sx={{ pt: 0.2, minWidth: 46, textAlign: 'right' }}>
                {isRunning && (
                    <Chip label="Live" size="small" sx={{
                        bgcolor: `${C.brown}18`, color: C.brown,
                        fontWeight: 800, fontSize: 10, height: 18,
                        animation: 'blink 1.3s ease-in-out infinite',
                        '@keyframes blink': {
                            '0%,100%': { opacity: 1 },
                            '50%': { opacity: 0.3 },
                        },
                    }} />
                )}
                {isDone && (
                    <Typography variant="caption" fontWeight={700}
                        color={C.success} sx={{ fontSize: 11 }}>
                        Done
                    </Typography>
                )}
            </Box>
        </Box>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// AgentModal — triple-agent (TMA → PRA → RAA) pipeline visualiser
// ─────────────────────────────────────────────────────────────────────────────
function AgentModal({ open, paymentData, onClose }) {
    const [statuses, setStatuses]         = useState({});
    const [botPhase, setBotPhase]         = useState('idle');
    const [tmaDecision, setTmaDecision]   = useState(null);
    const [praDecision, setPraDecision]   = useState(null);
    const [praScore, setPraScore]         = useState(null);
    const [praTypology, setPraTypology]   = useState(null);
    const [raaVerdict, setRaaVerdict]     = useState(null);
    const [raaScore, setRaaScore]         = useState(null);
    const [abaVerdict, setAbaVerdict]     = useState(null);
    const [abaGatewayAction, setAbaGatewayAction] = useState(null);
    const [abaCaseId, setAbaCaseId]       = useState(null);
    const [abaStages, setAbaStages]       = useState([]);
    const [currentAgent, setCurrentAgent] = useState('tma');  // 'tma' | 'pra' | 'raa' | 'aba' | 'done'
    const [progress, setProgress]         = useState(0);
    const [raaStages, setRaaStages]       = useState([]);
    const [activeId, setActiveId]         = useState(null);
    const [showFlagConfirm, setShowFlagConfirm] = useState(false);
    const [showBlockNotify, setShowBlockNotify] = useState(false);
    const timers = useRef([]);

    const clearAll = () => { timers.current.forEach(clearTimeout); timers.current = []; };
    useEffect(() => () => clearAll(), []);

    useEffect(() => {
        if (!open || !paymentData) {
            // Reset state when modal closes
            clearAll();
            return;
        }

        clearAll();
        setStatuses({});
        setBotPhase('running');
        setTmaDecision(null);
        setPraDecision(null);
        setPraScore(null);
        setPraTypology(null);
        setRaaVerdict(null);
        setRaaScore(null);
        setAbaVerdict(null);
        setAbaGatewayAction(null);
        setAbaCaseId(null);
        setAbaStages([]);
        setCurrentAgent('tma');
        setProgress(0);
        setRaaStages([]);
        setActiveId(null);
        setShowFlagConfirm(false);
        setShowBlockNotify(false);

        // Give DOM a moment to render the modal
        const initialDelay = setTimeout(() => {
            let elapsed = 0;

            ALL_STEPS.forEach((step, idx) => {
                const t1 = setTimeout(() => {
                    setActiveId(step.id);
                    setStatuses(prev => ({ ...prev, [step.id]: 'running' }));
                    setProgress(Math.round((idx / TOTAL_STEPS) * 100));

                    // When first PRA step starts, mark TMA as fully done and fetch its result
                    if (step.id === PRA_STEPS[0].id) {
                        setCurrentAgent('pra');
                        _fetchTmaResult(paymentData.payment_id);
                    }
                }, elapsed);
                timers.current.push(t1);

                elapsed += step.ms;

                const t2 = setTimeout(() => {
                    setStatuses(prev => ({ ...prev, [step.id]: 'done' }));
                    setProgress(Math.round(((idx + 1) / TOTAL_STEPS) * 100));

                    if (idx === ALL_STEPS.length - 1) {
                        _fetchPraResult(paymentData.payment_id);
                        _fetchRaaResult(paymentData.payment_id);
                    }
                }, elapsed);
                timers.current.push(t2);
            });
        }, 100);  // Small delay to ensure modal is fully rendered
        timers.current.push(initialDelay);

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open, paymentData]);

    const getStatus = (stepId) => {
        if (statuses[stepId] === 'done')    return 'done';
        if (statuses[stepId] === 'running') return 'running';
        return 'pending';
    };

    const _fetchTmaResult = async (paymentId) => {
        // First, check if TMA decision is already in paymentData from the response
        if (paymentData?.tma?.decision) {
            setTmaDecision(paymentData.tma.decision);
            return;
        }
        
        // Otherwise, fetch from API (for cases where modal reopens)
        for (let attempt = 0; attempt < 3; attempt++) {
            try {
                const res = await api.get(`/fraud-alert/${paymentId}`);
                if (res.data?.decision) {
                    setTmaDecision(res.data.decision || 'ALLOW');
                    return;
                }
            } catch {
                await new Promise(r => setTimeout(r, 1500));
            }
        }
        setTmaDecision('ALLOW');
    };

    const _fetchPraResult = async (paymentId) => {
        // PRA writes asynchronously — give it up to ~15s
        for (let attempt = 0; attempt < 6; attempt++) {
            await new Promise(r => setTimeout(r, 2500));
            try {
                const res = await api.get(`/pattern-alert/${paymentId}`);
                if (res.data?.decision) {
                    setPraDecision(res.data.decision);
                    setPraScore(res.data.pattern_score ?? null);
                    setPraTypology(res.data.typology_code ?? null);
                    return;
                }
            } catch (err) {
                if (err.response?.status === 404) continue;  // still processing
            }
        }
        // PRA timed out — show 'Pending' state
        setPraDecision('PENDING');
    };

    const _fetchRaaResult = async (paymentId) => {
        setCurrentAgent('raa');
        for (let attempt = 0; attempt < 30; attempt++) {
            await new Promise(r => setTimeout(r, 1000));
            try {
                const res = await api.get(`/raa/alerts/${paymentId}`);
                if (res.status === 202) {
                    if (res.data?.stages && Array.isArray(res.data.stages)) {
                        setRaaStages(res.data.stages);
                        const numDone = ALL_STEPS.length + res.data.stages.filter(s => s.status === 'done' || s.status === 'error').length;
                        setProgress(Math.round((numDone / TOTAL_STEPS) * 100));
                    }
                    continue;
                }
                if (res.data?.raa_verdict) {
                    setRaaVerdict(res.data.raa_verdict);
                    setRaaScore(res.data.final_raa_score ?? null);
                    // After RAA completes, fetch ABA result
                    _fetchAbaResult(paymentId, res.data.raa_verdict);
                    return;
                }
            } catch (err) {
                if (err.response?.status === 202 && err.response.data?.stages && Array.isArray(err.response.data.stages)) {
                    setRaaStages(err.response.data.stages);
                    const numDone = ALL_STEPS.length + err.response.data.stages.filter(s => s.status === 'done' || s.status === 'error').length;
                    setProgress(Math.round((numDone / TOTAL_STEPS) * 100));
                }
            }
        }
        // RAA timed out — still try ABA
        _fetchAbaResult(paymentId, null);
    };

    const _fetchAbaResult = async (paymentId, raaVerdictValue) => {
        setCurrentAgent('aba');

        // Simulate ABA stages animation
        const baseProgress = ((TMA_STEPS.length + PRA_STEPS.length + RAA_STEPS.length) / TOTAL_STEPS) * 100;

        for (let i = 0; i < ABA_STEPS.length; i++) {
            await new Promise(r => setTimeout(r, 400));
            setAbaStages(prev => [...prev, { stage: ABA_STEPS[i].id, status: 'done' }]);
            setProgress(Math.round(baseProgress + ((i + 1) / ABA_STEPS.length) * (100 - baseProgress)));
        }

        // Poll ABA health to check if processing is complete
        for (let attempt = 0; attempt < 10; attempt++) {
            try {
                const res = await api.get('/aba/health');
                if (res.data?.status === 'ok') {
                    // ABA is healthy, processing should be complete
                    break;
                }
            } catch {
                // Continue polling
            }
            await new Promise(r => setTimeout(r, 500));
        }

        // Set final ABA state based on RAA verdict
        if (raaVerdictValue === 'BLOCK') {
            setAbaVerdict('BLOCK');
            setAbaGatewayAction('STOPPED');
            setShowBlockNotify(true);
        } else if (raaVerdictValue === 'ALERT') {
            setAbaVerdict('ALERT');
            setAbaGatewayAction('HELD');
        } else if (raaVerdictValue === 'FLAG') {
            setAbaVerdict('FLAG');
            setAbaGatewayAction('APPROVE_AFTER_CONFIRM');
            setShowFlagConfirm(true);
        } else {
            setAbaVerdict('ALLOW');
            setAbaGatewayAction('APPROVE');
        }

        setCurrentAgent('done');
        setBotPhase('done');
        setProgress(100);
    };

    const getRaaStatus = (stepId) => {
        if (currentAgent === 'done' || currentAgent === 'aba') return 'done';
        const stage = raaStages.find(s => s.stage === stepId);
        if (!stage) return 'pending';
        if (stage.status === 'done' || stage.status === 'error') return 'done';
        if (stage.status === 'processing') return 'running';
        return 'pending';
    };

    const getAbaStatus = (stepId) => {
        if (currentAgent === 'done') return 'done';
        if (currentAgent !== 'aba') return 'pending';
        const stage = abaStages.find(s => s.stage === stepId);
        if (!stage) {
            // Check if this is the next step to run
            const idx = ABA_STEPS.findIndex(s => s.id === stepId);
            if (idx === abaStages.length) return 'running';
            return 'pending';
        }
        return 'done';
    };


    const tmaDc    = tmaDecision && tmaDecision !== 'PENDING' ? DECISION_CFG[tmaDecision] : null;
    const praDc    = praDecision && praDecision !== 'PENDING' ? DECISION_CFG[praDecision] : null;
    const isDone   = botPhase === 'done';
    const praLabel = currentAgent === 'pra' ? 'Pattern Agent running…' :
                     currentAgent === 'done' ? 'Pattern Agent complete' : '';

    return (
        <>
        <Dialog
            open={open}
            maxWidth="sm"
            fullWidth
            disableEscapeKeyDown={!isDone}
            onClose={(_, reason) => {
                if (!isDone) return;
                if (reason !== 'backdropClick') onClose();
            }}
            PaperProps={{
                sx: {
                    borderRadius: 4,
                    overflow: 'hidden',
                    background: 'linear-gradient(160deg, #fffcf9 0%, #fdf6ef 100%)',
                    boxShadow: '0 32px 80px rgba(127,85,57,0.18)',
                    zIndex: 1300,  // Ensure modal is on top
                }
            }}
            sx={{
                '& .MuiBackdrop-root': {
                    backgroundColor: 'rgba(0, 0, 0, 0.5)',
                    zIndex: 1299,  // Backdrop slightly below dialog
                }
            }}
        >
            <DialogContent sx={{ p: 0 }}>

                {/* ── Modal header bar ── */}
                <Box sx={{
                    bgcolor: C.brown, px: 3, py: 2,
                    display: 'flex', alignItems: 'center', gap: 1.5,
                }}>
                    <SmartToyIcon sx={{ color: C.brownLight }} />
                    <Box sx={{ flex: 1 }}>
                        <Typography fontWeight={800} color="white" fontSize={15}>
                            Jatayu — Multi-Agent Fraud Pipeline
                        </Typography>
                        <Typography variant="caption" color={C.brownLight} sx={{ opacity: 0.85 }}>
                            {isDone
                                ? 'All agents complete'
                                : currentAgent === 'aba'
                                    ? 'Alert & Block Agent · Executing Actions'
                                    : currentAgent === 'raa'
                                        ? `Risk Agent · Polling Background Stages`
                                        : currentAgent === 'pra'
                                            ? `Pattern Agent · Step ${PRA_STEPS.findIndex(s => s.id === activeId) + 1} of ${PRA_STEPS.length}`
                                            : `Monitoring Agent · Step ${TMA_STEPS.findIndex(s => s.id === activeId) + 1} of ${TMA_STEPS.length}`
                            }
                        </Typography>
                    </Box>
                    {isDone && (
                        <IconButton size="small" onClick={onClose}
                            sx={{ color: C.brownLight, '&:hover': { bgcolor: 'rgba(255,255,255,0.1)' } }}>
                            ✕
                        </IconButton>
                    )}
                </Box>

                <Box sx={{ px: 3, py: 3 }}>

                    {/* ── Bot + progress bar ── */}
                    <Box sx={{ textAlign: 'center', mb: 3 }}>
                        <AnimatedBot phase={botPhase} decision={raaVerdict || praDecision || tmaDecision} />

                        <Typography variant="body2" color="text.secondary"
                            fontWeight={500} mt={1.5} mb={1.5}>
                            {isDone
                                ? 'All agents completed analysis'
                                : currentAgent === 'raa'
                                    ? 'Risk Assessment Agent running…'
                                    : currentAgent === 'pra'
                                        ? 'Pattern Recognition Agent running…'
                                        : 'Transaction Monitoring Agent running…'
                            }
                        </Typography>

                        <Box sx={{ mx: 'auto', maxWidth: 360 }}>
                            <LinearProgress
                                variant="determinate"
                                value={progress}
                                sx={{
                                    height: 7, borderRadius: 4,
                                    bgcolor: '#f0e0d0',
                                    '& .MuiLinearProgress-bar': {
                                        borderRadius: 4,
                                        background: `linear-gradient(90deg, ${C.brown} 0%, ${C.brownMid} 100%)`,
                                        transition: 'transform 0.6s ease',
                                    },
                                }}
                            />
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                                <Typography variant="caption" color="text.secondary">
                                    Multi-Agent Pipeline
                                </Typography>
                                <Typography variant="caption" color={C.brown} fontWeight={700}>
                                    {progress}%
                                </Typography>
                            </Box>
                        </Box>
                    </Box>

                    <Divider sx={{ borderColor: '#f0e0d0', mb: 2 }} />

                    {/* ── AGENT 1: Transaction Monitoring Agent ── */}
                    <Box sx={{ mb: 1 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <Typography variant="caption" fontWeight={800}
                                textTransform="uppercase" letterSpacing={0.8}
                                color={currentAgent === 'tma' ? C.brown : C.success}>
                                {currentAgent === 'tma' ? '⚡' : '✅'} Agent 1 — Transaction Monitor
                            </Typography>
                            {currentAgent !== 'tma' && (
                                <Chip label="Complete" size="small"
                                    sx={{ bgcolor: `${C.success}18`, color: C.success,
                                          fontWeight: 700, fontSize: 10, height: 18 }} />
                            )}
                            {currentAgent === 'tma' && (
                                <Chip label="Running" size="small"
                                    sx={{ bgcolor: `${C.brown}18`, color: C.brown,
                                          fontWeight: 700, fontSize: 10, height: 18,
                                          animation: 'blink 1.3s ease-in-out infinite',
                                          '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } } }} />
                            )}
                        </Box>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                            {TMA_STEPS.map(step => (
                                <StepRow key={step.id} step={step} status={getStatus(step.id)} />
                            ))}
                        </Box>
                    </Box>

                    {/* ── TMA Verdict ── */}
                    {tmaDc && (
                        <Box sx={{
                            mt: 2, mb: 1, p: 2, borderRadius: 2.5,
                            bgcolor: tmaDc.bg, border: `1.5px solid ${tmaDc.border}`,
                            animation: 'slideUp 0.45s cubic-bezier(0.34,1.56,0.64,1)',
                            '@keyframes slideUp': {
                                from: { opacity: 0, transform: 'translateY(12px)' },
                                to: { opacity: 1, transform: 'translateY(0)' },
                            },
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Typography variant="caption" fontWeight={700}
                                    color="text.secondary" textTransform="uppercase" letterSpacing={0.7}>
                                    🔎 TMA Verdict
                                </Typography>
                                <Chip label={tmaDecision} size="small"
                                    sx={{ bgcolor: tmaDc.color, color: 'white', fontWeight: 800, fontSize: 11 }} />
                            </Box>
                            <Typography variant="body2" color="text.secondary" mt={0.5}>
                                {tmaDc.msg}
                            </Typography>
                        </Box>
                    )}

                    {/* ── Agent divider ── */}
                    {(currentAgent === 'pra' || currentAgent === 'done') && (
                        <Box sx={{ my: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ flex: 1, height: '1px', bgcolor: '#f0e0d0' }} />
                            <Typography variant="caption" color={C.brownMid} fontWeight={700} fontSize={11}>
                                ▼ Pattern Recognition Agent
                            </Typography>
                            <Box sx={{ flex: 1, height: '1px', bgcolor: '#f0e0d0' }} />
                        </Box>
                    )}

                    {/* ── AGENT 2: Pattern Recognition Agent ── */}
                    {(currentAgent === 'pra' || currentAgent === 'done') && (
                        <Box sx={{ mb: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Typography variant="caption" fontWeight={800}
                                    textTransform="uppercase" letterSpacing={0.8}
                                    color={currentAgent === 'pra' ? C.brown : C.success}>
                                    {currentAgent === 'done' ? '✅' : '⚡'} Agent 2 — Pattern Recogniser
                                </Typography>
                                {currentAgent === 'done' && (
                                    <Chip label="Complete" size="small"
                                        sx={{ bgcolor: `${C.success}18`, color: C.success,
                                              fontWeight: 700, fontSize: 10, height: 18 }} />
                                )}
                                {currentAgent === 'pra' && (
                                    <Chip label="Running" size="small"
                                        sx={{ bgcolor: `${C.brown}18`, color: C.brown,
                                              fontWeight: 700, fontSize: 10, height: 18,
                                              animation: 'blink 1.3s ease-in-out infinite',
                                              '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } } }} />
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {PRA_STEPS.map(step => (
                                    <StepRow key={step.id} step={step} status={getStatus(step.id)} />
                                ))}
                            </Box>
                        </Box>
                    )}

                    {/* ── PRA Pattern Verdict ── */}
                    {isDone && (
                        <Box sx={{
                            mt: 2, p: 2, borderRadius: 2.5,
                            bgcolor: praDc ? praDc.bg : 'rgba(150,150,150,0.07)',
                            border: `1.5px solid ${praDc ? praDc.border : '#ddd'}`,
                            animation: 'slideUp 0.45s cubic-bezier(0.34,1.56,0.64,1)',
                            '@keyframes slideUp': {
                                from: { opacity: 0, transform: 'translateY(12px)' },
                                to: { opacity: 1, transform: 'translateY(0)' },
                            },
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                <Typography variant="caption" fontWeight={700}
                                    color="text.secondary" textTransform="uppercase" letterSpacing={0.7}>
                                    🕸️ Pattern Verdict
                                </Typography>
                                {praDc
                                    ? <Chip label={praDecision} size="small"
                                           sx={{ bgcolor: praDc.color, color: 'white', fontWeight: 800, fontSize: 11 }} />
                                    : <Chip label="Processing…" size="small"
                                           sx={{ bgcolor: '#e0e0e0', color: '#666', fontWeight: 700, fontSize: 11 }} />
                                }
                                {praScore !== null && (
                                    <Chip label={`Score: ${praScore}`} size="small"
                                        sx={{ bgcolor: `${C.brownMid}18`, color: C.brownMid,
                                              fontWeight: 700, fontSize: 11 }} />
                                )}
                                {praTypology && (
                                    <Chip label={praTypology} size="small" variant="outlined"
                                        sx={{ borderColor: C.brownLight, color: C.brown,
                                              fontWeight: 600, fontSize: 10 }} />
                                )}
                            </Box>
                            <Typography variant="body2" color="text.secondary" mt={0.5}>
                                {praDc
                                    ? praDc.msg
                                    : 'Pattern analysis across multiple transactions is still processing. Check back shortly.'}
                            </Typography>
                        </Box>
                    )}

                    {/* ── Agent divider ── */}
                    {(currentAgent === 'raa' || currentAgent === 'done') && (
                        <Box sx={{ my: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Box sx={{ flex: 1, height: '1px', bgcolor: '#f0e0d0' }} />
                            <Typography variant="caption" color={C.brownMid} fontWeight={700} fontSize={11}>
                                ▼ Risk Assessment Agent
                            </Typography>
                            <Box sx={{ flex: 1, height: '1px', bgcolor: '#f0e0d0' }} />
                        </Box>
                    )}

                    {/* ── AGENT 3: Risk Assessment Agent ── */}
                    {(currentAgent === 'raa' || currentAgent === 'done') && (
                        <Box sx={{ mb: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Typography variant="caption" fontWeight={800}
                                    textTransform="uppercase" letterSpacing={0.8}
                                    color={currentAgent === 'raa' ? C.brown : C.success}>
                                    {currentAgent === 'done' ? '✅' : '⚡'} Agent 3 — Risk Assessor
                                </Typography>
                                {currentAgent === 'done' && (
                                    <Chip label="Complete" size="small"
                                        sx={{ bgcolor: `${C.success}18`, color: C.success,
                                              fontWeight: 700, fontSize: 10, height: 18 }} />
                                )}
                                {currentAgent === 'raa' && (
                                    <Chip label="Running" size="small"
                                        sx={{ bgcolor: `${C.brown}18`, color: C.brown,
                                              fontWeight: 700, fontSize: 10, height: 18,
                                              animation: 'blink 1.3s ease-in-out infinite',
                                              '@keyframes blink': { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } } }} />
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {RAA_STEPS.map(step => (
                                    <StepRow key={step.id} step={step} status={getRaaStatus(step.id)} />
                                ))}
                            </Box>
                        </Box>
                    )}

                    {/* ── AGENT 4: Alert & Block Agent ── */}
                    {(currentAgent === 'aba' || currentAgent === 'done') && (
                        <Box sx={{
                            mt: 2, p: 2.5, borderRadius: 2.5,
                            bgcolor: 'rgba(236,64,122,0.04)',
                            border: '1.5px solid rgba(236,64,122,0.25)',
                            animation: 'slideUp 0.35s ease-out',
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                <Typography fontWeight={800} fontSize={14} color="#ec407a">
                                    ▼ Alert & Block Agent
                                </Typography>
                                {currentAgent === 'aba' && (
                                    <Chip label="Running" size="small"
                                        sx={{ bgcolor: 'rgba(236,64,122,0.2)', color: '#ec407a',
                                              fontWeight: 700, fontSize: 10, height: 18,
                                              animation: 'blink 1.3s ease-in-out infinite' }} />
                                )}
                                {currentAgent === 'done' && (
                                    <Chip label="Complete" size="small"
                                        sx={{ bgcolor: '#4caf5020', color: '#4caf50', fontWeight: 700, fontSize: 10, height: 18 }} />
                                )}
                            </Box>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                                {ABA_STEPS.map(step => (
                                    <StepRow key={step.id} step={step} status={getAbaStatus(step.id)} />
                                ))}
                            </Box>
                        </Box>
                    )}

                    {/* ── ABA Gateway Action ── */}
                    {isDone && abaGatewayAction && (
                        <Box sx={{
                            mt: 2, p: 2, borderRadius: 2.5,
                            bgcolor: abaGatewayAction === 'STOPPED' ? 'rgba(244,67,54,0.08)' :
                                     abaGatewayAction === 'HELD' ? 'rgba(255,152,0,0.08)' :
                                     abaGatewayAction === 'APPROVE_AFTER_CONFIRM' ? 'rgba(25,118,210,0.08)' :
                                     'rgba(76,175,80,0.08)',
                            border: `1.5px solid ${
                                abaGatewayAction === 'STOPPED' ? 'rgba(244,67,54,0.4)' :
                                abaGatewayAction === 'HELD' ? 'rgba(255,152,0,0.4)' :
                                abaGatewayAction === 'APPROVE_AFTER_CONFIRM' ? 'rgba(25,118,210,0.4)' :
                                'rgba(76,175,80,0.4)'
                            }`,
                            animation: 'slideUp 0.45s cubic-bezier(0.34,1.56,0.64,1)',
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                <Typography variant="caption" fontWeight={700}
                                    color="text.secondary" textTransform="uppercase" letterSpacing={0.7}>
                                    🚦 Gateway Action
                                </Typography>
                                <Chip label={abaGatewayAction.replace(/_/g, ' ')} size="small"
                                    sx={{
                                        bgcolor: abaGatewayAction === 'STOPPED' ? '#f44336' :
                                                 abaGatewayAction === 'HELD' ? '#ff9800' :
                                                 abaGatewayAction === 'APPROVE_AFTER_CONFIRM' ? '#1976d2' :
                                                 '#4caf50',
                                        color: 'white', fontWeight: 800, fontSize: 11
                                    }} />
                                {abaCaseId && (
                                    <Chip label={`Case: ${abaCaseId}`} size="small"
                                        sx={{ bgcolor: '#f4433618', color: '#f44336', fontWeight: 700, fontSize: 10 }} />
                                )}
                            </Box>
                        </Box>
                    )}

                    {/* ── RAA Verdict ── */}
                    {isDone && raaVerdict && (
                        <Box sx={{
                            mt: 2, p: 2, borderRadius: 2.5,
                            bgcolor: DECISION_CFG[raaVerdict]?.bg || 'rgba(150,150,150,0.07)',
                            border: `1.5px solid ${DECISION_CFG[raaVerdict]?.border || '#ddd'}`,
                            animation: 'slideUp 0.45s cubic-bezier(0.34,1.56,0.64,1)',
                            '@keyframes slideUp': {
                                from: { opacity: 0, transform: 'translateY(12px)' },
                                to: { opacity: 1, transform: 'translateY(0)' },
                            },
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                                <Typography variant="caption" fontWeight={700}
                                    color="text.secondary" textTransform="uppercase" letterSpacing={0.7}>
                                    ⚖️ Final Verdict
                                </Typography>
                                <Chip label={raaVerdict} size="small"
                                    sx={{ bgcolor: DECISION_CFG[raaVerdict]?.color || '#666', color: 'white', fontWeight: 800, fontSize: 11 }} />
                                {raaScore !== null && (
                                    <Chip label={`Score: ${raaScore}`} size="small"
                                        sx={{ bgcolor: `${C.brownMid}18`, color: C.brownMid,
                                              fontWeight: 700, fontSize: 11 }} />
                                )}
                            </Box>
                        </Box>
                    )}

                    {/* ── Payment summary card ── */}
                    {paymentData && (
                        <Box sx={{
                            mt: 2.5, p: 2, borderRadius: 2,
                            bgcolor: '#f9f4f0',
                            border: '1px solid #f0e0d0',
                        }}>
                            <Typography variant="caption" color="text.secondary"
                                fontWeight={700} textTransform="uppercase"
                                letterSpacing={0.8} display="block" mb={1.25}>
                                Payment Summary
                            </Typography>

                            {[
                                {
                                    label: 'Amount Sent',
                                    value: `₹${parseFloat(paymentData.amount)
                                        .toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
                                    bold: true,
                                    color: C.brown,
                                },
                                {
                                    label: 'Recipient',
                                    value: paymentData.recipient,
                                    mono: true,
                                },
                                {
                                    label: 'New Balance',
                                    value: `₹${parseFloat(paymentData.new_balance)
                                        .toLocaleString('en-IN', { minimumFractionDigits: 2 })}`,
                                    bold: true,
                                },
                                {
                                    label: 'Payment ID',
                                    value: paymentData.payment_id,
                                    mono: true,
                                    small: true,
                                },
                            ].map(row => (
                                <Box key={row.label} sx={{
                                    display: 'flex', justifyContent: 'space-between',
                                    alignItems: 'center', mb: 0.75,
                                }}>
                                    <Typography variant="body2" color="text.secondary">
                                        {row.label}
                                    </Typography>
                                    <Typography
                                        variant={row.small ? 'caption' : 'body2'}
                                        fontWeight={row.bold ? 700 : 500}
                                        color={row.color || 'text.primary'}
                                        sx={row.mono ? { fontFamily: 'monospace' } : {}}
                                    >
                                        {row.value}
                                    </Typography>
                                </Box>
                            ))}
                        </Box>
                    )}

                    {/* ── Automated Broker Note ── */}
                    {isDone && (
                        <Box sx={{
                            mt: 2, p: 2, borderRadius: 2,
                            bgcolor: `${C.info}08`,
                            border: `1px solid ${C.info}40`,
                        }}>
                            <Typography variant="caption" fontWeight={700} color={C.info} display="block" mb={0.5}>
                                🔍 Automated Action Broker
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                The final decision has been handed off to the Action Broker. You can view full diagnostic details and regulatory reports in your{' '}
                                <Typography
                                    component="span"
                                    fontWeight={700}
                                    color={C.brown}
                                    onClick={() => {
                                        onClose();
                                        navigate('/risk');
                                    }}
                                    sx={{ cursor: 'pointer', textDecoration: 'underline' }}
                                >
                                    Risk Evaluation
                                </Typography>
                                {' '}page.
                            </Typography>
                        </Box>
                    )}

                    {/* ── Back to Dashboard button — only after done ── */}
                    {isDone && (
                        <Button
                            fullWidth variant="contained"
                            onClick={onClose}
                            sx={{
                                mt: 2.5, bgcolor: C.brown,
                                fontWeight: 700, py: 1.3,
                                borderRadius: 2, fontSize: 14,
                                '&:hover': { bgcolor: C.brownMid },
                                animation: 'fadeIn 0.4s ease 0.15s both',
                                '@keyframes fadeIn': {
                                    from: { opacity: 0 },
                                    to: { opacity: 1 },
                                },
                            }}
                        >
                            Back to Dashboard
                        </Button>
                    )}

                </Box>
            </DialogContent>
        </Dialog>

        {/* FLAG Confirmation Modal */}
        <FlagConfirmationModal
            open={showFlagConfirm}
            onClose={() => setShowFlagConfirm(false)}
            paymentId={paymentData?.payment_id}
            amount={paymentData?.amount ? `₹${parseFloat(paymentData.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : ''}
            recipient={paymentData?.recipient}
            score={raaScore}
            requiresMfa={raaScore >= 45 && raaScore <= 50}
            onConfirm={() => {
                toast.success('Transaction confirmed');
            }}
            onDispute={() => {
                toast.info('Transaction escalated for review');
            }}
        />

        {/* BLOCK Notification Modal */}
        <BlockNotificationModal
            open={showBlockNotify}
            onClose={() => setShowBlockNotify(false)}
            paymentId={paymentData?.payment_id}
            amount={paymentData?.amount ? `₹${parseFloat(paymentData.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : ''}
            recipient={paymentData?.recipient}
            score={raaScore}
            accountFrozen={true}
            caseId={abaCaseId}
            typology={praTypology}
        />
        </>
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// PaymentPage
// ─────────────────────────────────────────────────────────────────────────────

export default function PaymentPage() {
    const navigate = useNavigate();

    const [profile, setProfile] = useState(null);
    const [pageLoading, setPageLoading] = useState(true);
    const [paymentMode, setPaymentMode] = useState('netbanking');
    const [recipientAcc, setRecipientAcc] = useState('');
    const [upiId, setUpiId] = useState('');
    const [amount, setAmount] = useState('');
    const [description, setDescription] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const [paymentData, setPaymentData] = useState(null);

    // ── OTP verification state (for ALERT verdict) ────────────────────────
    const [showOtpModal, setShowOtpModal] = useState(false);
    const [otpValue, setOtpValue] = useState('');
    const [otpLoading, setOtpLoading] = useState(false);
    const [otpError, setOtpError] = useState('');
    const [pendingPayment, setPendingPayment] = useState(null);  // { payment_id, amount, recipient, ... }
    const [otpAttemptsRemaining, setOtpAttemptsRemaining] = useState(3);
    const [resendCooldown, setResendCooldown] = useState(0);

    // Fetch profile (for balance display + account number)
    const fetchProfile = useCallback(async () => {
        try {
            const res = await api.get('/me');
            setProfile(res.data);
            // Redirect away if security not complete
            if (!res.data.security_complete) {
                toast.error('Please complete security setup first.');
                navigate('/customer-dashboard');
            }
        } catch {
            toast.error('Failed to load profile.');
            navigate('/customer-dashboard');
        } finally {
            setPageLoading(false);
        }
    }, [navigate]);

    useEffect(() => { fetchProfile(); }, [fetchProfile]);

    const handleSubmit = async () => {
        // ── Client-side validation ─────────────────────────────────────
        const recipient = paymentMode === 'netbanking'
            ? recipientAcc.trim()
            : upiId.trim();

        if (!recipient) {
            toast.error(paymentMode === 'netbanking'
                ? 'Please enter a recipient account number.'
                : 'Please enter a UPI ID.');
            return;
        }
        if (!amount || isNaN(amount) || parseFloat(amount) <= 0) {
            toast.error('Please enter a valid amount.');
            return;
        }
        if (parseFloat(amount) > parseFloat(profile?.balance ?? 0)) {
            toast.error(`Insufficient balance. Available: ₹${parseFloat(profile.balance)
                .toLocaleString('en-IN', { minimumFractionDigits: 2 })}`);
            return;
        }

        setSubmitting(true);
        try {
            const res = await api.post('/payment', {
                amount: parseFloat(amount),
                description: description.trim() || 'Payment',
                recipient_account: recipient,
            });

            // ── Check for ALERT verdict (HTTP 202 — verification required) ──
            if (res.status === 202 || res.data?.status === 'verification_required') {
                // Payment is held — OTP sent to customer, show OTP modal
                setPendingPayment({
                    payment_id: res.data.payment_id,
                    amount: res.data.amount,
                    recipient: res.data.recipient,
                    current_balance: res.data.current_balance,
                    message: res.data.message,
                    tma: res.data.tma,
                });
                setOtpValue('');
                setOtpError('');
                setOtpAttemptsRemaining(3);
                setResendCooldown(60);  // 60 second cooldown before resend
                setShowOtpModal(true);
                toast.info('Transaction requires verification. Please enter the OTP sent to your registered email.');

                // Reset form fields
                setRecipientAcc('');
                setUpiId('');
                setAmount('');
                setDescription('');
                return;
            }

            // Payment committed — open agent modal
            setPaymentData(res.data);
            setShowModal(true);

            // Reset form
            setRecipientAcc('');
            setUpiId('');
            setAmount('');
            setDescription('');

        } catch (err) {
            const errs = err.response?.data?.errors;
            const msg = err.response?.data?.message;
            if (errs?.length) errs.forEach(e => toast.error(e));
            else toast.error(msg || 'Payment failed. Please try again.');
        } finally {
            setSubmitting(false);
        }
    };

    const handleModalClose = () => {
        setShowModal(false);
        setPaymentData(null);  // Clear payment data
        navigate('/customer-dashboard');
    };

    // ── OTP Resend Cooldown Timer ─────────────────────────────────────────
    useEffect(() => {
        if (resendCooldown > 0) {
            const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000);
            return () => clearTimeout(timer);
        }
    }, [resendCooldown]);

    // ── OTP Verification Handler ──────────────────────────────────────────
    const handleVerifyOtp = async () => {
        if (!otpValue || otpValue.length !== 6) {
            setOtpError('Please enter a 6-digit OTP.');
            return;
        }

        setOtpLoading(true);
        setOtpError('');

        try {
            const res = await api.post('/payment/verify-otp', {
                payment_id: pendingPayment.payment_id,
                otp: otpValue,
            });

            // OTP verified — payment committed
            if (res.data?.status === 'approved') {
                toast.success('Payment verified and processed successfully!');
                setShowOtpModal(false);
                setPendingPayment(null);
                setOtpValue('');

                // Update profile balance from response
                if (res.data.new_balance !== undefined) {
                    setProfile(prev => ({ ...prev, balance: res.data.new_balance }));
                }

                // Open agent modal to show pipeline progress
                setPaymentData({
                    payment_id: pendingPayment.payment_id,
                    amount: pendingPayment.amount,
                    new_balance: res.data.new_balance,
                    recipient: pendingPayment.recipient,
                    tma: pendingPayment.tma,
                });
                setShowModal(true);
            }
        } catch (err) {
            const status = err.response?.status;
            const data = err.response?.data;

            if (status === 401) {
                // Wrong OTP
                const remaining = data?.attempts_remaining ?? (otpAttemptsRemaining - 1);
                setOtpAttemptsRemaining(remaining);
                setOtpError(data?.message || `Incorrect OTP. ${remaining} attempt(s) remaining.`);
                setOtpValue('');
            } else if (status === 403) {
                // Max attempts reached — payment rejected, account soft-locked
                toast.error(data?.message || 'Payment rejected after too many failed attempts.');
                setShowOtpModal(false);
                setPendingPayment(null);
                setOtpValue('');
                navigate('/customer-dashboard');
            } else if (status === 410) {
                // OTP expired or payment session expired
                toast.error(data?.message || 'Payment session expired. Please initiate a new payment.');
                setShowOtpModal(false);
                setPendingPayment(null);
                setOtpValue('');
            } else {
                setOtpError(data?.message || 'Verification failed. Please try again.');
            }
        } finally {
            setOtpLoading(false);
        }
    };

    // ── OTP Resend Handler ────────────────────────────────────────────────
    const handleResendOtp = async () => {
        if (resendCooldown > 0) return;

        try {
            await api.post('/payment/resend-otp', {
                payment_id: pendingPayment.payment_id,
            });
            toast.success('OTP resent to your registered email.');
            setResendCooldown(60);  // Reset cooldown
            setOtpValue('');
            setOtpError('');
        } catch (err) {
            toast.error(err.response?.data?.message || 'Could not resend OTP. Please try again.');
        }
    };

    // ── OTP Modal Close Handler ───────────────────────────────────────────
    const handleOtpModalClose = () => {
        // Closing without verifying means payment stays held (will eventually expire)
        setShowOtpModal(false);
        setPendingPayment(null);
        setOtpValue('');
        setOtpError('');
        toast.warning('Payment verification cancelled. The held payment will expire.');
        navigate('/customer-dashboard');
    };

    if (pageLoading) {
        return (
            <Box sx={{
                display: 'flex', justifyContent: 'center', alignItems: 'center',
                minHeight: '100vh', bgcolor: C.bg
            }}>
                <CircularProgress sx={{ color: C.brown }} />
            </Box>
        );
    }

    return (
        <Box sx={{ minHeight: '100vh', bgcolor: C.bg, pb: 6 }}>

            {/* ── Header — identical to CustomerDashboard ── */}
            <Box sx={{ bgcolor: C.brown, color: C.brownLight, py: 2.5, px: 3 }}>
                <Container maxWidth="md">
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                            <AccountBalanceIcon />
                            <Typography fontWeight={800} fontSize={18}>EagleTrust Bank</Typography>
                        </Box>
                        <Button
                            size="small" variant="outlined"
                            startIcon={<ArrowBackIcon />}
                            onClick={() => navigate('/customer-dashboard')}
                            sx={{
                                color: C.brownLight, borderColor: C.brownLight,
                                '&:hover': { bgcolor: 'rgba(230,204,178,0.1)' },
                            }}
                        >
                            Dashboard
                        </Button>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="md" sx={{ mt: 4 }}>
                <Grid container spacing={3}>

                    {/* ── LEFT: Payment form ── */}
                    <Grid item xs={12} md={7}>
                        <Paper elevation={0} sx={{
                            borderRadius: 3, p: 3.5,
                            boxShadow: '0 4px 24px rgba(127,85,57,0.1)',
                        }}>

                            {/* Title row */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
                                <Avatar sx={{
                                    bgcolor: `${C.brown}18`, width: 46, height: 46,
                                }}>
                                    <SendIcon sx={{ color: C.brown, fontSize: 22 }} />
                                </Avatar>
                                <Box>
                                    <Typography fontWeight={800} color={C.brown} fontSize={18}>
                                        Make a Payment
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        Secure · Instant · AI-Monitored
                                    </Typography>
                                </Box>
                            </Box>

                            <Divider sx={{ borderColor: '#f0e0d0', mb: 3 }} />

                            {/* Payment mode toggle */}
                            <Typography variant="caption" color="text.secondary"
                                fontWeight={700} textTransform="uppercase"
                                letterSpacing={0.8} display="block" mb={1}>
                                Payment Method
                            </Typography>
                            <ToggleButtonGroup
                                value={paymentMode}
                                exclusive
                                onChange={(_, val) => { if (val) setPaymentMode(val); }}
                                fullWidth
                                sx={{ mb: 3 }}
                            >
                                {[
                                    { value: 'netbanking', label: 'Net Banking', Icon: AccountBalanceIcon },
                                    { value: 'upi', label: 'UPI', Icon: PhoneAndroidIcon },
                                ].map(({ value, label, Icon }) => (
                                    <ToggleButton key={value} value={value} sx={{
                                        py: 1.2, gap: 1,
                                        fontWeight: 600, fontSize: 13,
                                        borderColor: '#e0c8b0',
                                        color: 'text.secondary',
                                        '&.Mui-selected': {
                                            bgcolor: `${C.brown}12`,
                                            color: C.brown,
                                            borderColor: C.brown,
                                            fontWeight: 700,
                                        },
                                        '&.Mui-selected:hover': { bgcolor: `${C.brown}1c` },
                                    }}>
                                        <Icon sx={{ fontSize: 18 }} />
                                        {label}
                                    </ToggleButton>
                                ))}
                            </ToggleButtonGroup>

                            {/* Form fields */}
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

                                {paymentMode === 'netbanking' ? (
                                    <TextField
                                        fullWidth
                                        label="Recipient Account Number"
                                        placeholder="Enter 12-digit account number"
                                        value={recipientAcc}
                                        onChange={e =>
                                            setRecipientAcc(
                                                e.target.value.replace(/\D/g, '').slice(0, 12)
                                            )
                                        }
                                        inputProps={{ maxLength: 12 }}
                                        helperText="Enter the exact account number registered with EagleTrust"
                                        InputProps={{
                                            startAdornment: (
                                                <AccountBalanceIcon sx={{
                                                    mr: 1, color: '#c0a080', fontSize: 20,
                                                }} />
                                            ),
                                        }}
                                        sx={{
                                            '& .MuiOutlinedInput-root': {
                                                '&:hover fieldset': { borderColor: C.brownMid },
                                                '&.Mui-focused fieldset': { borderColor: C.brown },
                                            },
                                            '& label.Mui-focused': { color: C.brown },
                                        }}
                                    />
                                ) : (
                                    <TextField
                                        fullWidth
                                        label="UPI ID"
                                        placeholder="e.g. name@ybl or phone@upi"
                                        value={upiId}
                                        onChange={e => setUpiId(e.target.value)}
                                        helperText="Enter the recipient's registered UPI ID"
                                        InputProps={{
                                            startAdornment: (
                                                <PhoneAndroidIcon sx={{
                                                    mr: 1, color: '#c0a080', fontSize: 20,
                                                }} />
                                            ),
                                        }}
                                        sx={{
                                            '& .MuiOutlinedInput-root': {
                                                '&:hover fieldset': { borderColor: C.brownMid },
                                                '&.Mui-focused fieldset': { borderColor: C.brown },
                                            },
                                            '& label.Mui-focused': { color: C.brown },
                                        }}
                                    />
                                )}

                                <TextField
                                    fullWidth
                                    label="Amount (₹)"
                                    type="number"
                                    placeholder="0.00"
                                    value={amount}
                                    onChange={e => setAmount(e.target.value)}
                                    inputProps={{ min: 1, max: 100000, step: 0.01 }}
                                    helperText="Min ₹1 · Max ₹1,00,000 per transaction"
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            '&:hover fieldset': { borderColor: C.brownMid },
                                            '&.Mui-focused fieldset': { borderColor: C.brown },
                                        },
                                        '& label.Mui-focused': { color: C.brown },
                                    }}
                                />

                                <TextField
                                    fullWidth
                                    label="Description (optional)"
                                    placeholder="e.g. Rent, Groceries, Loan repayment"
                                    value={description}
                                    onChange={e => setDescription(e.target.value)}
                                    inputProps={{ maxLength: 100 }}
                                    sx={{
                                        '& .MuiOutlinedInput-root': {
                                            '&:hover fieldset': { borderColor: C.brownMid },
                                            '&.Mui-focused fieldset': { borderColor: C.brown },
                                        },
                                        '& label.Mui-focused': { color: C.brown },
                                    }}
                                />
                            </Box>

                            <Divider sx={{ borderColor: '#f0e0d0', my: 3 }} />

                            {/* Submit */}
                            <Button
                                fullWidth
                                variant="contained"
                                size="large"
                                disabled={submitting}
                                onClick={handleSubmit}
                                startIcon={submitting
                                    ? <CircularProgress size={18} color="inherit" />
                                    : <SendIcon />
                                }
                                sx={{
                                    bgcolor: C.brown,
                                    fontWeight: 700,
                                    py: 1.5,
                                    borderRadius: 2,
                                    fontSize: 15,
                                    '&:hover': { bgcolor: C.brownMid },
                                    '&.Mui-disabled': { bgcolor: '#d0b898', color: 'white' },
                                }}
                            >
                                {submitting ? 'Processing...' : 'Send Payment'}
                            </Button>

                        </Paper>
                    </Grid>

                    {/* ── RIGHT: Info panels ── */}
                    <Grid item xs={12} md={5}>
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>

                            {/* Balance card */}
                            <Paper elevation={0} sx={{
                                borderRadius: 3, p: 3,
                                boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                                    <AccountBalanceWalletIcon sx={{ color: C.brownMid, fontSize: 20 }} />
                                    <Typography variant="caption" color="text.secondary"
                                        fontWeight={700} textTransform="uppercase" letterSpacing={0.8}>
                                        Available Balance
                                    </Typography>
                                </Box>
                                <Typography variant="h4" fontWeight={800} color={C.brown}>
                                    ₹{parseFloat(profile?.balance ?? 0)
                                        .toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </Typography>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.8, mt: 1 }}>
                                    <Typography variant="caption" color="text.secondary"
                                        sx={{ fontFamily: 'monospace', letterSpacing: 1.5 }}>
                                        {profile?.account_number}
                                    </Typography>
                                    <Tooltip title="Copy account number">
                                        <IconButton size="small"
                                            onClick={() => {
                                                navigator.clipboard.writeText(
                                                    profile?.account_number_raw ||
                                                    profile?.account_number
                                                );
                                                toast.info('Account number copied!', { autoClose: 1500 });
                                            }}
                                        >
                                            <ContentCopyIcon sx={{ fontSize: 14, color: C.brownMid }} />
                                        </IconButton>
                                    </Tooltip>
                                </Box>
                            </Paper>

                            {/* Jatayu AI notice */}
                            <Paper elevation={0} sx={{
                                borderRadius: 3, p: 3,
                                boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
                                bgcolor: `${C.brown}08`,
                                border: `1px solid ${C.brownLight}`,
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                                    <SmartToyIcon sx={{ color: C.brown, fontSize: 20 }} />
                                    <Typography fontWeight={700} color={C.brown} fontSize={14}>
                                        Jatayu AI Active
                                    </Typography>
                                    <Chip label="Live" size="small" sx={{
                                        ml: 'auto',
                                        bgcolor: `${C.success}18`,
                                        color: C.success,
                                        fontWeight: 800, fontSize: 10, height: 20,
                                        animation: 'blink 2s ease-in-out infinite',
                                        '@keyframes blink': {
                                            '0%,100%': { opacity: 1 },
                                            '50%': { opacity: 0.4 },
                                        },
                                    }} />
                                </Box>
                                <Typography variant="caption" color="text.secondary"
                                    lineHeight={1.7}>
                                    Every payment is evaluated by a <strong>multi-agent AI pipeline</strong>:
                                    the Transaction Monitoring Agent (7 stages), followed by
                                    Pattern Recognition (4 stages) and Risk Assessment (7 stages).
                                    Each stage completes live in the monitoring modal.
                                </Typography>

                                <Divider sx={{ borderColor: '#f0e0d0', my: 2 }} />

                                {/* Mini pipeline preview */}
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                                {/* TMA steps */}
                                {TMA_STEPS.map(step => (
                                    <Box key={step.id} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Typography fontSize={13}>{step.icon}</Typography>
                                        <Typography variant="caption" color="text.secondary" fontWeight={500}>
                                            {step.label}
                                        </Typography>
                                    </Box>
                                ))}
                                {/* PRA steps */}
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                                    <Typography fontSize={11} color={C.brownMid} fontWeight={700}
                                        sx={{ borderLeft: `2px solid ${C.brownLight}`, pl: 0.75, ml: 1.5 }}>
                                        Pattern Agent
                                    </Typography>
                                </Box>
                                {PRA_STEPS.map(step => (
                                    <Box key={step.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 1.5 }}>
                                        <Typography fontSize={13}>{step.icon}</Typography>
                                        <Typography variant="caption" color="text.secondary" fontWeight={500}>
                                            {step.label}
                                        </Typography>
                                    </Box>
                                ))}
                                </Box>
                            </Paper>

                            {/* Security badge */}
                            <Paper elevation={0} sx={{
                                borderRadius: 3, p: 2.5,
                                boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
                            }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <SecurityIcon sx={{ color: C.success, fontSize: 20 }} />
                                    <Typography variant="body2" fontWeight={700}
                                        color="text.primary">
                                        Bank-grade Security
                                    </Typography>
                                </Box>
                                <Typography variant="caption" color="text.secondary"
                                    display="block" mt={0.75} lineHeight={1.7}>
                                    Payments are processed with atomic DB transactions.
                                    All data is encrypted in transit.
                                </Typography>
                            </Paper>

                        </Box>
                    </Grid>

                </Grid>
            </Container>

            {/* ── Agent monitoring modal ── */}
            <AgentModal
                open={showModal}
                paymentData={paymentData}
                onClose={handleModalClose}
            />

            {/* ── OTP Verification Modal (for ALERT verdict) ── */}
            <Dialog
                open={showOtpModal}
                onClose={handleOtpModalClose}
                maxWidth="xs"
                fullWidth
                PaperProps={{
                    sx: {
                        borderRadius: 3,
                        boxShadow: '0 16px 64px rgba(127,85,57,0.2)',
                    }
                }}
            >
                <DialogContent sx={{ p: 4, textAlign: 'center' }}>
                    {/* Warning header */}
                    <Box sx={{
                        width: 64, height: 64, borderRadius: '50%',
                        bgcolor: 'rgba(255,152,0,0.12)', mx: 'auto', mb: 2,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <SecurityIcon sx={{ fontSize: 32, color: C.warning }} />
                    </Box>

                    <Typography variant="h6" fontWeight={700} color="text.primary" mb={1}>
                        Transaction Verification Required
                    </Typography>

                    <Typography variant="body2" color="text.secondary" mb={3}>
                        {pendingPayment?.message || 'We have sent an OTP to your registered email. Please enter it below to confirm this transaction.'}
                    </Typography>

                    {/* Transaction summary */}
                    <Paper elevation={0} sx={{
                        bgcolor: C.cream, borderRadius: 2, p: 2, mb: 3,
                        border: `1px solid ${C.brownLight}`,
                    }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                            <Typography variant="body2" color="text.secondary">Amount</Typography>
                            <Typography variant="body2" fontWeight={700} color={C.brown}>
                                ₹{pendingPayment?.amount?.toLocaleString('en-IN', { minimumFractionDigits: 2 }) || '0.00'}
                            </Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="body2" color="text.secondary">To</Typography>
                            <Typography variant="body2" fontWeight={600}>
                                {pendingPayment?.recipient || 'Unknown'}
                            </Typography>
                        </Box>
                    </Paper>

                    {/* OTP Input */}
                    <TextField
                        fullWidth
                        label="Enter 6-digit OTP"
                        value={otpValue}
                        onChange={(e) => {
                            const val = e.target.value.replace(/\D/g, '').slice(0, 6);
                            setOtpValue(val);
                            setOtpError('');
                        }}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && otpValue.length === 6) {
                                handleVerifyOtp();
                            }
                        }}
                        error={!!otpError}
                        helperText={otpError || `${otpAttemptsRemaining} attempt(s) remaining`}
                        disabled={otpLoading}
                        inputProps={{
                            maxLength: 6,
                            style: { textAlign: 'center', letterSpacing: '0.5em', fontSize: '1.5rem', fontWeight: 700 },
                        }}
                        sx={{
                            mb: 2,
                            '& .MuiOutlinedInput-root': {
                                borderRadius: 2,
                                '&.Mui-focused fieldset': { borderColor: C.brown },
                            },
                            '& .MuiInputLabel-root.Mui-focused': { color: C.brown },
                        }}
                    />

                    {/* Verify Button */}
                    <Button
                        fullWidth
                        variant="contained"
                        size="large"
                        onClick={handleVerifyOtp}
                        disabled={otpLoading || otpValue.length !== 6}
                        sx={{
                            bgcolor: C.brown, py: 1.5, borderRadius: 2, fontWeight: 700,
                            '&:hover': { bgcolor: C.brownMid },
                            '&.Mui-disabled': { bgcolor: 'rgba(127,85,57,0.3)' },
                        }}
                    >
                        {otpLoading ? (
                            <CircularProgress size={24} sx={{ color: 'white' }} />
                        ) : (
                            'Verify & Complete Payment'
                        )}
                    </Button>

                    {/* Resend OTP */}
                    <Box sx={{ mt: 2 }}>
                        <Button
                            variant="text"
                            size="small"
                            onClick={handleResendOtp}
                            disabled={resendCooldown > 0}
                            sx={{ color: C.brown, textTransform: 'none' }}
                        >
                            {resendCooldown > 0
                                ? `Resend OTP in ${resendCooldown}s`
                                : 'Resend OTP'}
                        </Button>
                    </Box>

                    {/* Cancel link */}
                    <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mt: 2, cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                        onClick={handleOtpModalClose}
                    >
                        Cancel Transaction
                    </Typography>
                </DialogContent>
            </Dialog>

        </Box>
    );
}