import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider, CssBaseline } from '@mui/material';
import theme from './theme';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import CustomerDashboard from './pages/CustomerDashboardPage';
import UpdateProfile     from './pages/UpdateProfilePage';
import PaymentPage from './pages/PaymentPage';
import RiskEvaluationPage from './pages/RiskEvaluationPage';
import TransactionHistoryPage from './pages/TransactionHistoryPage';
import AdminLoginPage from './pages/AdminLoginPage';
import AdminDashboardPage from './pages/AdminDashboardPage';

function App() {
    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <BrowserRouter>
                <Routes>
                    <Route path="/" element={<HomePage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                    <Route path="/customer-dashboard" element={<CustomerDashboard />} />
                    <Route path="/dashboard" element={<CustomerDashboard />} />
                    <Route path="/profile" element={<UpdateProfile />} />
                    <Route path="/payment" element={<PaymentPage />} />
                    <Route path="/risk" element={<RiskEvaluationPage />} />
                    <Route path="/transactions" element={<TransactionHistoryPage />} />
                    <Route path="/goadmin" element={<AdminLoginPage />} />
                    <Route path="/admin/dashboard" element={<AdminDashboardPage />} />
                </Routes>
            </BrowserRouter>
        </ThemeProvider>
    );
}

export default App;
