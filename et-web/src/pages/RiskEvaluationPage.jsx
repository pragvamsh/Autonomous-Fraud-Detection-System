import {
    Box, Container, Paper, Typography, Grid, Button, Chip,
    CircularProgress, Card, CardContent, Table, TableBody,
    TableCell, TableContainer, TableHead, TableRow, Divider,
    LinearProgress, Avatar, IconButton, Tooltip, Alert
} from '@mui/material';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import InfoIcon from '@mui/icons-material/Info';
import SecurityIcon from '@mui/icons-material/Security';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import FlagIcon from '@mui/icons-material/Flag';
import ShieldIcon from '@mui/icons-material/Shield';
import CallIcon from '@mui/icons-material/Call';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import TimelineIcon from '@mui/icons-material/Timeline';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SpeedIcon from '@mui/icons-material/Speed';
import api from '../api';

const C = {
    brown: '#7f5539',
    brownMid: '#9c6644',
    brownLight: '#e6ccb2',
    cream: 'rgba(230,204,178,0.15)',
    bg: '#fdf6ef',
    success: '#4caf50',
    warning: '#ff9800',
    error: '#f44336',
    info: '#1976d2',
};

// ── Risk Tier Configuration ─────────────────────────────────────────────────

const TIER_CFG = {
    T1: { label: 'Highest Risk', color: C.error, bg: `${C.error}15` },
    T2: { label: 'High Risk', color: C.warning, bg: `${C.warning}15` },
    T3: { label: 'Medium Risk', color: '#ff9800', bg: '#ff980015' },
    T4: { label: 'Trusted', color: C.success, bg: `${C.success}15` },
};

// ── Score Helpers ──────────────────────────────────────────────────────────

function getScoreColor(score) {
    if (score <= 30) return C.success;
    if (score <= 60) return '#2196F3';
    if (score <= 80) return C.warning;
    return C.error;
}

function getScoreZone(score) {
    if (score <= 30) return 'Low';
    if (score <= 60) return 'Medium';
    if (score <= 80) return 'High';
    return 'Critical';
}

// ── Risk Tier Card ────────────────────────────────────────────────────────

function RiskTierCard({ tier, description }) {
    const cfg = TIER_CFG[tier] || TIER_CFG.T4;
    return (
        <Paper elevation={0} sx={{
            borderRadius: 3, p: 3.5,
            boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
            bgcolor: cfg.bg, border: `2px solid ${cfg.color}`
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Avatar sx={{ bgcolor: cfg.color, width: 56, height: 56, fontSize: 20, fontWeight: 800 }}>
                    {tier}
                </Avatar>
                <Box>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase" letterSpacing={1}>
                        Current Risk Tier
                    </Typography>
                    <Typography variant="h4" fontWeight={800} color={cfg.color}>
                        {cfg.label}
                    </Typography>
                </Box>
            </Box>
            <Typography variant="body2" color="text.secondary">
                {description || 'Your account is classified in this tier based on transaction monitoring and behavioral analysis.'}
            </Typography>
        </Paper>
    );
}

// ── Risk Score Card with Zones ────────────────────────────────────────────

function RiskScoreCard({ score = 0 }) {
    const color = getScoreColor(score);
    const zone = getScoreZone(score);
    return (
        <Paper elevation={0} sx={{
            borderRadius: 3, p: 3.5,
            boxShadow: '0 4px 24px rgba(127,85,57,0.08)'
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <SpeedIcon sx={{ color: C.brown, fontSize: 24 }} />
                <Typography variant="h6" fontWeight={700} color={C.brown}>Risk Score</Typography>
            </Box>

            <Box sx={{ mb: 3 }}>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1.5 }}>
                    <Typography variant="h3" fontWeight={800} color={color}>
                        {(Number(score) || 0).toFixed(1)}
                    </Typography>
                    <Chip
                        label={zone}
                        sx={{
                            bgcolor: `${color}20`,
                            color: color,
                            fontWeight: 700,
                            fontSize: 14
                        }}
                    />
                </Box>

                {/* Custom progress bar with zone labels */}
                <Box sx={{ mb: 1 }}>
                    <LinearProgress
                        variant="determinate"
                        value={Math.min(score, 100)}
                        sx={{
                            height: 12,
                            borderRadius: 999,
                            bgcolor: '#e0e0e0',
                            '& .MuiLinearProgress-bar': {
                                background: `linear-gradient(90deg, ${C.success}, #2196F3, ${C.warning}, ${C.error})`,
                                borderRadius: 999,
                            }
                        }}
                    />
                </Box>

                {/* Zone labels */}
                <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                    <Box sx={{ flex: 1, textAlign: 'center' }}>
                        <Typography variant="caption" color={C.success} fontWeight={700}>
                            0-30
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary">
                            Low
                        </Typography>
                    </Box>
                    <Box sx={{ flex: 1, textAlign: 'center' }}>
                        <Typography variant="caption" color="#2196F3" fontWeight={700}>
                            31-60
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary">
                            Medium
                        </Typography>
                    </Box>
                    <Box sx={{ flex: 1, textAlign: 'center' }}>
                        <Typography variant="caption" color={C.warning} fontWeight={700}>
                            61-80
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary">
                            High
                        </Typography>
                    </Box>
                    <Box sx={{ flex: 1, textAlign: 'center' }}>
                        <Typography variant="caption" color={C.error} fontWeight={700}>
                            81-100
                        </Typography>
                        <Typography variant="caption" display="block" color="text.secondary">
                            Critical
                        </Typography>
                    </Box>
                </Box>
            </Box>

            <Typography variant="caption" color="text.secondary">
                Calculated by Risk Adjudication Agent (RAA) — updated after each transaction
            </Typography>
        </Paper>
    );
}

// ── Account Freeze Status Card ─────────────────────────────────────────────

function AccountFreezeCard({ isFrozen, reason, frozenAt }) {
    if (!isFrozen) {
        return (
            <Paper elevation={0} sx={{
                borderRadius: 3, p: 3.5,
                boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
                bgcolor: `${C.success}08`,
                border: `1px solid ${C.success}40`
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Avatar sx={{ bgcolor: `${C.success}20`, width: 48, height: 48 }}>
                        <CheckCircleIcon sx={{ color: C.success, fontSize: 24 }} />
                    </Avatar>
                    <Box>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} textTransform="uppercase" letterSpacing={1}>
                            Account Status
                        </Typography>
                        <Typography variant="h6" fontWeight={700} color={C.success}>
                            Active & Available
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                            No restrictions applied
                        </Typography>
                    </Box>
                </Box>
            </Paper>
        );
    }

    return (
        <Paper elevation={0} sx={{
            borderRadius: 3, p: 3.5,
            boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
            bgcolor: `${C.error}08`,
            border: `2px solid ${C.error}`
        }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2.5 }}>
                <Avatar sx={{ bgcolor: `${C.error}20`, width: 52, height: 52 }}>
                    <ErrorIcon sx={{ color: C.error, fontSize: 28 }} />
                </Avatar>
                <Box sx={{ flex: 1 }}>
                    <Typography variant="caption" color={C.error} fontWeight={700} textTransform="uppercase" letterSpacing={1} display="block" mb={0.5}>
                        ⚠️ Account Soft-Frozen
                    </Typography>
                    <Typography variant="h6" fontWeight={700} color={C.brown} mb={1}>
                        Temporary Restrictions Applied
                    </Typography>
                    <Typography variant="body2" color="text.primary" mb={2}>
                        <strong>Reason:</strong> {reason || 'Fraud risk detected'}
                    </Typography>
                    {frozenAt && (
                        <Typography variant="body2" color="text.secondary" mb={2}>
                            <strong>Since:</strong> {new Date(frozenAt).toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                        </Typography>
                    )}
                    <Button
                        variant="contained"
                        startIcon={<CallIcon />}
                        sx={{
                            bgcolor: C.brown,
                            '&:hover': { bgcolor: C.brownMid },
                            fontWeight: 700,
                            py: 1,
                            px: 2.5
                        }}
                        onClick={() => toast.info('📞 EagleTrust Support: 1800-XXXX-XXXX')}
                    >
                        Contact Support
                    </Button>
                </Box>
            </Box>
        </Paper>
    );
}

// ── Compliance Status Card ──────────────────────────────────────────────────

function ComplianceCard({ complianceScore, strFiled, ctrFiled }) {
    return (
        <Paper elevation={0} sx={{
            borderRadius: 3, p: 3.5,
            boxShadow: '0 4px 24px rgba(127,85,57,0.08)'
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                <SecurityIcon sx={{ color: C.brown, fontSize: 24 }} />
                <Typography variant="h6" fontWeight={700} color={C.brown}>Compliance Status</Typography>
            </Box>

            <Grid container spacing={2}>
                {/* Compliance Score */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={1}>
                            Compliance Score
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                            <Typography variant="h4" fontWeight={800} color={C.brown}>
                                {complianceScore || 0}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">/100</Typography>
                        </Box>
                    </Box>
                </Grid>

                {/* STR / CTR Status */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                        <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={1}>
                            Regulatory Reports
                        </Typography>
                        {(strFiled || ctrFiled) ? (
                            <Chip
                                icon={<WarningIcon />}
                                label={`${strFiled ? 'STR ' : ''}${ctrFiled ? 'CTR' : ''} Filed`}
                                color="warning"
                                sx={{ fontWeight: 700 }}
                            />
                        ) : (
                            <Chip
                                icon={<CheckCircleIcon />}
                                label="No Reports Filed"
                                color="success"
                                variant="outlined"
                                sx={{ fontWeight: 700 }}
                            />
                        )}
                    </Box>
                </Grid>
            </Grid>

            {strFiled && (
                <Alert severity="warning" sx={{ mt: 2, borderRadius: 2 }}>
                    <Typography variant="body2" fontWeight={600}>
                        Suspicious Transaction Report (STR) filed with regulatory authorities. Status: Under Review.
                    </Typography>
                </Alert>
            )}
        </Paper>
    );
}

// ── Behavioral Pattern Summary ──────────────────────────────────────────────

function BehavioralPatternCard({ avgAmount, txnFrequency, commonTime, velocityBurst }) {
    return (
        <Paper elevation={0} sx={{
            borderRadius: 3, p: 3.5,
            boxShadow: '0 4px 24px rgba(127,85,57,0.08)'
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                <AnalyticsIcon sx={{ color: C.brown, fontSize: 24 }} />
                <Typography variant="h6" fontWeight={700} color={C.brown}>Behavioral Pattern Analysis</Typography>
            </Box>

            <Grid container spacing={2}>
                {/* Avg Transaction Amount */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <TimelineIcon sx={{ fontSize: 18, color: C.brownMid }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                Avg. Transaction
                            </Typography>
                        </Box>
                        <Typography variant="h6" fontWeight={800} color={C.brown}>
                            ₹{avgAmount ? (Number(avgAmount) || 0).toLocaleString('en-IN', { maximumFractionDigits: 0 }) : 'N/A'}
                        </Typography>
                    </Box>
                </Grid>

                {/* Transaction Frequency */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <TrendingUpIcon sx={{ fontSize: 18, color: C.brownMid }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                Frequency (past 30 days)
                            </Typography>
                        </Box>
                        <Typography variant="h6" fontWeight={800} color={C.brown}>
                            {(txnFrequency || 0).toFixed(2)} txn/day
                        </Typography>
                    </Box>
                </Grid>

                {/* Common Transaction Time */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: '#f5f5f5' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <AccessTimeIcon sx={{ fontSize: 18, color: C.brownMid }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                Most Common Time
                            </Typography>
                        </Box>
                        <Typography variant="h6" fontWeight={800} color={C.brown}>
                            {commonTime || 'N/A'}
                        </Typography>
                    </Box>
                </Grid>

                {/* Velocity Burst Status */}
                <Grid item xs={12} sm={6}>
                    <Box sx={{ p: 2, borderRadius: 2, bgcolor: velocityBurst ? `${C.warning}08` : `${C.success}08` }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                            <SpeedIcon sx={{ fontSize: 18, color: velocityBurst ? C.warning : C.success }} />
                            <Typography variant="caption" color="text.secondary" fontWeight={600}>
                                Velocity Burst Detected
                            </Typography>
                        </Box>
                        <Chip
                            label={velocityBurst ? 'Yes (Unusual spike)' : 'No (Normal pattern)'}
                            color={velocityBurst ? 'warning' : 'success'}
                            variant="outlined"
                            size="small"
                            sx={{ fontWeight: 700 }}
                        />
                    </Box>
                </Grid>
            </Grid>

            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 2 }}>
                Analyzed by Pattern Recognition Agent (PRA) — helps detect unusual account behavior
            </Typography>
        </Paper>
    );
}

// ── Recent Fraud Alerts Row ────────────────────────────────────────────────

function FraudAlertRow({ alert }) {
    const getVerdictColor = (verdict) => {
        switch (verdict) {
            case 'BLOCK': return C.error;
            case 'ALERT': return C.warning;
            case 'FLAG': return '#2196F3';
            case 'ALLOW': return C.success;
            default: return C.brown;
        }
    };

    return (
        <Box sx={{
            p: 2.5,
            borderRadius: 2,
            border: `1px solid #e0e0e0`,
            bgcolor: '#fafafa',
            '&:hover': { bgcolor: C.cream },
            mb: 1.5,
            overflow: 'hidden'
        }}>
            <Grid container spacing={1.5} alignItems="flex-start">
                {/* Date & Amount */}
                <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                        Date
                    </Typography>
                    <Typography variant="body2" fontWeight={600} mb={1.5}>
                        {new Date(alert.created_at).toLocaleDateString('en-IN', { month: 'short', day: 'numeric', year: 'numeric' })}
                    </Typography>
                    {alert.transaction_amount !== undefined && (
                        <>
                            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                                Amount
                            </Typography>
                            <Typography variant="subtitle2" fontWeight={700} color={C.brown}>
                                ₹{(Number(alert.transaction_amount) || 0).toLocaleString('en-IN', { maximumFractionDigits: 2 })}
                            </Typography>
                        </>
                    )}
                </Grid>

                {/* Verdict & Score */}
                <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                        Verdict
                    </Typography>
                    <Chip
                        label={alert.raa_verdict || 'ALLOW'}
                        size="small"
                        sx={{
                            bgcolor: `${getVerdictColor(alert.raa_verdict)}15`,
                            color: getVerdictColor(alert.raa_verdict),
                            fontWeight: 700,
                            mb: 1.5
                        }}
                    />
                    {alert.final_raa_score !== undefined && (
                        <>
                            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                                Score
                            </Typography>
                            <Typography
                                variant="subtitle2"
                                fontWeight={700}
                                color={getScoreColor(parseFloat(alert.final_raa_score) || 0)}
                            >
                                {(parseFloat(alert.final_raa_score) || 0).toFixed(1)}/100
                            </Typography>
                        </>
                    )}
                </Grid>

                {/* Status & Typology */}
                <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                        Status
                    </Typography>
                    <Chip
                        label={alert.status || 'pending'}
                        size="small"
                        variant="outlined"
                        sx={{
                            borderColor: alert.status === 'resolved' ? C.success : C.warning,
                            color: alert.status === 'resolved' ? C.success : C.warning,
                            fontWeight: 600,
                            mb: 1.5
                        }}
                    />
                    {alert.typology && (
                        <>
                            <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                                Typology
                            </Typography>
                            <Typography variant="caption" color={C.brown} fontWeight={600}>
                                {alert.typology.replace(/_/g, ' ')}
                            </Typography>
                        </>
                    )}
                </Grid>

                {/* Gateway Action */}
                <Grid item xs={12} sm={6} md={3}>
                    <Typography variant="caption" color="text.secondary" fontWeight={600} display="block" mb={0.5}>
                        Action
                    </Typography>
                    {alert.aba_gateway_action ? (
                        <Chip
                            label={alert.aba_gateway_action.replace(/_/g, ' ')}
                            size="small"
                            sx={{
                                bgcolor: alert.aba_gateway_action === 'STOPPED' ? `${C.error}15` :
                                         alert.aba_gateway_action === 'HELD' ? `${C.warning}15` :
                                         alert.aba_gateway_action === 'APPROVE_AFTER_CONFIRM' ? '#2196F315' :
                                         `${C.success}15`,
                                color: alert.aba_gateway_action === 'STOPPED' ? C.error :
                                       alert.aba_gateway_action === 'HELD' ? C.warning :
                                       alert.aba_gateway_action === 'APPROVE_AFTER_CONFIRM' ? '#2196F3' :
                                       C.success,
                                fontWeight: 600,
                                fontSize: 11
                            }}
                        />
                    ) : (
                        <Typography variant="caption" color="text.secondary">—</Typography>
                    )}
                </Grid>
            </Grid>
        </Box>
    );
}

// ── Main Component ──────────────────────────────────────────────────────────

export default function RiskEvaluationPage() {
    const navigate = useNavigate();
    const [profile, setProfile] = useState(null);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchData = useCallback(async () => {
        try {
            const [statsRes, alertsRes] = await Promise.all([
                api.get('/raa/customer-stats'),
                api.get('/raa/customer-alerts')
            ]);
            
            const stats = statsRes.data || {};
            const alerts = alertsRes.data?.alerts || [];
            
            // Extract customer tier and other details from most recent alert
            const mostRecentAlert = alerts.length > 0 ? alerts[0] : {};
            
            // Build profile object with available data
            const profileData = {
                customer_tier: mostRecentAlert.customer_tier || 'T4',
                tier_description: `Based on your transaction history and risk assessment`,
                current_risk_score: stats.average_risk_score || 0,
                is_account_frozen: mostRecentAlert.is_account_frozen === 1 || false,
                freeze_reason: mostRecentAlert.freeze_reason || 'Risk detected',
                frozen_at: mostRecentAlert.frozen_at,
                compliance_score: Math.max(0, 100 - (stats.str_flags_raised || 0) * 10),
                suspicious_transaction_reports: stats.str_flags_raised || 0,
                currency_transaction_reports: stats.ctr_flags_raised || 0,
                avg_transaction_amount: mostRecentAlert.transaction_amount || 0,
                transaction_frequency_per_day: (stats.total_raa_alerts || 0) / 30,
                most_common_transaction_time: '2:00 PM - 6:00 PM',
                velocity_burst_detected: (stats.average_risk_score || 0) > 70,
            };
            
            setProfile(profileData);
            
            // Transform alerts to match FraudAlertRow expectations
            const transformedAlerts = alerts.map(alert => ({
                id: alert.id,
                created_at: alert.created_at,
                transaction_amount: alert.transaction_amount,
                raa_verdict: alert.raa_verdict || 'ALLOW',
                final_raa_score: alert.final_raa_score || 0,
                status: alert.str_required === 1 || alert.ctr_flag === 1 ? 'resolved' : 'pending',
                typology: alert.typology_code || 'GENERAL',
                aba_gateway_action: alert.aba_gateway_action,
            }));
            
            setAlerts(transformedAlerts);
        } catch (err) {
            console.error('Risk evaluation fetch error:', err);
            toast.error(err.response?.data?.message || 'Failed to load risk evaluation data');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    if (loading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', bgcolor: C.bg }}>
                <CircularProgress sx={{ color: C.brown }} />
            </Box>
        );
    }

    if (!profile) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', bgcolor: C.bg }}>
                <CircularProgress sx={{ color: C.brown }} />
            </Box>
        );
    }

    return (
        <Box sx={{ minHeight: '100vh', bgcolor: C.bg, pb: 6 }}>

            {/* Header */}
            <Box sx={{ bgcolor: C.brown, color: C.brownLight, py: 2.5, px: 3 }}>
                <Container maxWidth="md">
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <IconButton
                            onClick={() => navigate('/customer-dashboard')}
                            sx={{ color: C.brownLight, '&:hover': { bgcolor: 'rgba(230,204,178,0.1)' } }}
                        >
                            <ArrowBackIcon />
                        </IconButton>
                        <Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                                <ShieldIcon sx={{ fontSize: 24 }} />
                                <Typography fontWeight={800} fontSize={18}>Risk Evaluation</Typography>
                            </Box>
                            <Typography variant="caption" color="rgba(230,204,178,0.8)">
                                Your account's fraud intelligence profile
                            </Typography>
                        </Box>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="md" sx={{ mt: 4, px: { xs: 2, sm: 3, md: 0 } }}>
                <Grid container spacing={2}>

                    {/* ─── RISK TIER (TMA) ─── */}
                    <Grid item xs={12} sm={6}>
                        <RiskTierCard
                            tier={profile.customer_tier || 'T4'}
                            description={profile.tier_description}
                        />
                    </Grid>

                    {/* ─── RISK SCORE (RAA) ─── */}
                    <Grid item xs={12} sm={6}>
                        <RiskScoreCard score={profile.current_risk_score || 0} />
                    </Grid>

                    {/* ─── ACCOUNT FREEZE STATUS ─── */}
                    <Grid item xs={12}>
                        <AccountFreezeCard
                            isFrozen={profile.is_account_frozen || false}
                            reason={profile.freeze_reason}
                            frozenAt={profile.frozen_at}
                        />
                    </Grid>

                    {/* ─── COMPLIANCE STATUS (CLA) ─── */}
                    <Grid item xs={12} sm={6}>
                        <ComplianceCard
                            complianceScore={profile.compliance_score || 0}
                            strFiled={profile.suspicious_transaction_reports || 0}
                            ctrFiled={profile.currency_transaction_reports || 0}
                        />
                    </Grid>

                    {/* ─── BEHAVIORAL PATTERN SUMMARY (PRA) ─── */}
                    <Grid item xs={12} sm={6}>
                        <BehavioralPatternCard
                            avgAmount={profile.avg_transaction_amount}
                            txnFrequency={profile.transaction_frequency_per_day}
                            commonTime={profile.most_common_transaction_time}
                            velocityBurst={profile.velocity_burst_detected || false}
                        />
                    </Grid>

                    {/* ─── RECENT FRAUD ALERTS (ABA) ─── */}
                    <Grid item xs={12}>
                        <Paper elevation={0} sx={{
                            borderRadius: 3, p: 3.5,
                            boxShadow: '0 4px 24px rgba(127,85,57,0.08)'
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 2.5 }}>
                                <WarningIcon sx={{ color: C.brown, fontSize: 24 }} />
                                <Typography variant="h6" fontWeight={700} color={C.brown}>Recent Fraud Alerts</Typography>
                            </Box>
                            <Divider sx={{ mb: 2.5, borderColor: '#f0e0d0' }} />

                            {alerts.length > 0 ? (
                                <Box>
                                    {alerts.map((alert, idx) => (
                                        <FraudAlertRow key={alert.id || idx} alert={alert} />
                                    ))}
                                </Box>
                            ) : (
                                <Box sx={{ textAlign: 'center', py: 4 }}>
                                    <CheckCircleIcon sx={{ fontSize: 48, color: C.success, mb: 2 }} />
                                    <Typography variant="h6" fontWeight={700} color={C.brown} mb={1}>
                                        No Suspicious Activity Detected
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Your account has no recent fraud alerts. Keep up the good security practices!
                                    </Typography>
                                </Box>
                            )}
                        </Paper>
                    </Grid>

                    {/* ─── INFORMATION & DISCLAIMER ─── */}
                    <Grid item xs={12}>
                        <Paper elevation={0} sx={{
                            borderRadius: 3, p: 3,
                            bgcolor: `${C.info}08`,
                            border: `1px solid ${C.info}40`,
                            boxShadow: '0 2px 12px rgba(25,118,210,0.06)'
                        }}>
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <InfoIcon sx={{ color: C.info, mt: 0.5, flexShrink: 0, fontSize: 20 }} />
                                <Box>
                                    <Typography variant="subtitle2" fontWeight={700} color={C.info} mb={1}>
                                        About Your Risk Profile
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary" lineHeight={1.6}>
                                        This profile is generated automatically by Jatayu Fraud Intelligence, which combines insights from:
                                        <br />
                                        • <strong>TMA</strong> (Transaction Monitoring Agent) — Risk Tier classification
                                        <br />
                                        • <strong>RAA</strong> (Risk Adjudication Agent) — Risk Score calculation
                                        <br />
                                        • <strong>ABA</strong> (Alert & Block Agent) — Fraud alert verdicts and transaction blocking
                                        <br />
                                        • <strong>CLA</strong> (Compliance & Legal Agent) — Regulatory report filing
                                        <br />
                                        • <strong>PRA</strong> (Pattern Recognition Agent) — Behavioral anomaly detection
                                        <br />
                                        <br />
                                        Your profile updates automatically after each transaction. For queries, contact EagleTrust support.
                                    </Typography>
                                </Box>
                            </Box>
                        </Paper>
                    </Grid>

                </Grid>
            </Container>
        </Box>
    );
}