import {
    Box, Container, Paper, Typography, CircularProgress,
    Table, TableBody, TableCell, TableContainer, TableHead,
    TableRow, Chip, IconButton
} from '@mui/material';
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import HistoryIcon from '@mui/icons-material/History';
import api from '../api';

const C = {
    brown: '#7f5539',
    brownMid: '#9c6644',
    brownLight: '#e6ccb2',
    cream: 'rgba(230,204,178,0.15)',
    bg: '#fdf6ef',
    success: '#4caf50',
    error: '#f44336',
};

export default function TransactionHistoryPage() {
    const navigate = useNavigate();
    const [transactions, setTransactions] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchTransactions = useCallback(async () => {
        try {
            const res = await api.get('/transactions?limit=50');
            setTransactions(res.data.transactions || []);
        } catch (err) {
            toast.error(err.response?.data?.message || 'Failed to load transaction history.');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchTransactions();
    }, [fetchTransactions]);

    const formatDate = (dateString) => {
        try {
            return new Date(dateString).toLocaleDateString('en-IN', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch {
            return dateString;
        }
    };

    const formatAmount = (amount, type) => {
        const prefix = type === 'CREDIT' ? '+' : '-';
        const formatted = amount.toLocaleString('en-IN', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        return `${prefix}₹${formatted}`;
    };

    if (loading) {
        return (
            <Box sx={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                minHeight: '100vh',
                bgcolor: C.bg
            }}>
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
                            sx={{ color: C.brownLight }}
                        >
                            <ArrowBackIcon />
                        </IconButton>
                        <AccountBalanceIcon />
                        <Typography fontWeight={800} fontSize={18}>
                            Transaction History
                        </Typography>
                    </Box>
                </Container>
            </Box>

            <Container maxWidth="md" sx={{ mt: 4 }}>
                {transactions.length === 0 ? (
                    <Paper elevation={0} sx={{
                        borderRadius: 3,
                        p: 4,
                        textAlign: 'center',
                        boxShadow: '0 4px 24px rgba(127,85,57,0.08)'
                    }}>
                        <HistoryIcon sx={{
                            fontSize: 48,
                            color: C.brownMid,
                            mb: 2,
                            opacity: 0.5
                        }} />
                        <Typography variant="h6" fontWeight={700} color={C.brown}>
                            No Transactions Yet
                        </Typography>
                        <Typography variant="body2" color="text.secondary" mt={1}>
                            Your transaction history will appear here once you add money or make payments.
                        </Typography>
                    </Paper>
                ) : (
                    <Paper elevation={0} sx={{
                        borderRadius: 3,
                        boxShadow: '0 4px 24px rgba(127,85,57,0.08)',
                        overflow: 'hidden'
                    }}>
                        <Box sx={{ p: 3 }}>
                            <Typography variant="h6" fontWeight={700} color={C.brown}>
                                All Transactions ({transactions.length})
                            </Typography>
                            <Typography variant="body2" color="text.secondary" mt={0.5}>
                                Showing your recent account activity
                            </Typography>
                        </Box>

                        <TableContainer>
                            <Table>
                                <TableHead sx={{ bgcolor: C.cream }}>
                                    <TableRow>
                                        <TableCell sx={{ fontWeight: 700, color: C.brown }}>
                                            Date & Time
                                        </TableCell>
                                        <TableCell sx={{ fontWeight: 700, color: C.brown }}>
                                            Type
                                        </TableCell>
                                        <TableCell sx={{ fontWeight: 700, color: C.brown }}>
                                            Description
                                        </TableCell>
                                        <TableCell sx={{ fontWeight: 700, color: C.brown }} align="right">
                                            Amount
                                        </TableCell>
                                        <TableCell sx={{ fontWeight: 700, color: C.brown }} align="right">
                                            Balance After
                                        </TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {transactions.map((txn) => (
                                        <TableRow
                                            key={txn.transaction_id}
                                            sx={{
                                                '&:hover': { bgcolor: C.cream },
                                                transition: 'background-color 0.2s'
                                            }}
                                        >
                                            <TableCell>
                                                <Typography variant="body2" fontWeight={500}>
                                                    {formatDate(txn.created_at)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell>
                                                <Chip
                                                    label={txn.type}
                                                    size="small"
                                                    sx={{
                                                        bgcolor: txn.type === 'CREDIT' ? `${C.success}15` : C.cream,
                                                        color: txn.type === 'CREDIT' ? C.success : C.brown,
                                                        fontWeight: 700,
                                                        fontSize: 11,
                                                        minWidth: 60
                                                    }}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <Typography
                                                    variant="body2"
                                                    sx={{
                                                        maxWidth: 280,
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap'
                                                    }}
                                                >
                                                    {txn.description}
                                                </Typography>
                                                <Typography variant="caption" color="text.secondary">
                                                    ID: {txn.transaction_id}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography
                                                    variant="body2"
                                                    fontWeight={700}
                                                    color={txn.type === 'CREDIT' ? C.success : C.brown}
                                                >
                                                    {formatAmount(txn.amount, txn.type)}
                                                </Typography>
                                            </TableCell>
                                            <TableCell align="right">
                                                <Typography variant="body2" color="text.secondary">
                                                    ₹{txn.balance_after.toLocaleString('en-IN', {
                                                        minimumFractionDigits: 2,
                                                        maximumFractionDigits: 2
                                                    })}
                                                </Typography>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                )}
            </Container>
        </Box>
    );
}
