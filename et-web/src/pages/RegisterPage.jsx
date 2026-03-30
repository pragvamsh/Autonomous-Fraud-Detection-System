import {
    Box, Container, Paper, Typography, TextField, Button,
    Link, Grid, MenuItem, Dialog, DialogTitle, DialogContent,
    DialogContentText, DialogActions, Radio, RadioGroup,
    FormControlLabel, FormControl, FormLabel, FormHelperText,
    CircularProgress, InputAdornment, Divider
} from '@mui/material';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import LockIcon from '@mui/icons-material/Lock';
import BadgeIcon from '@mui/icons-material/Badge';
import CreditCardIcon from '@mui/icons-material/CreditCard';
import { useState, useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';

export default function RegisterPage() {
    const [showConfirmModal, setShowConfirmModal] = useState(false);
    const [formData, setFormData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const navigate = useNavigate();
    const {
        register, handleSubmit, control, watch, setValue,
        formState: { errors }
    } = useForm({ defaultValues: { country: 'India', state: 'Telangana', gender: '', accountType: '' } })

    const watchAddress = watch('address', '');
    const watchAadhaar = watch('aadhaar', '');
    const watchPan = watch('pan', '');

    // Lock country and state fields
    useEffect(() => {
        setValue('country', 'India');
        setValue('state', 'Telangana');
    }, [setValue]);

    const handleConfirmSubmit = async () => {
        setIsLoading(true);
        try {
            const response = await fetch('http://localhost:5000/api/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include', // Enable session cookies
                body: JSON.stringify(formData)
            });
            const result = await response.json();

            if (response.ok) {
                setShowConfirmModal(false);

                toast.success('Registration successful! Redirecting...', { icon: '🎉', autoClose: 2000 });
                setTimeout(() => {
                    navigate('/customer-dashboard', {
                        state: {
                            startTour: true,
                            customerId: result.customer_id,
                            accountNumber: result.account_number,
                        }
                    });
                }, 2000);
            } else {
                if (result.errors && Array.isArray(result.errors)) {
                    result.errors.forEach((err) => toast.error(err));
                } else {
                    toast.error(result.message || 'Registration failed. Please try again.');
                }
            }
        } catch (error) {
            toast.error('Network error — backend may be unreachable. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    const SectionLabel = ({ children }) => (
        <Grid item xs={12}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 1 }}>
                <Divider sx={{ flex: 1, borderColor: '#e0c8b0' }} />
                <Typography variant="caption" sx={{ color: '#9c6644', fontWeight: 700, letterSpacing: 1, whiteSpace: 'nowrap', textTransform: 'uppercase' }}>
                    {children}
                </Typography>
                <Divider sx={{ flex: 1, borderColor: '#e0c8b0' }} />
            </Box>
        </Grid>
    );

    return (
        <Box
            sx={{
                minHeight: '100vh',
                background: 'linear-gradient(-45deg, #7f5539, #9c664433, #7f5539, #9c6644)',
                backgroundSize: '400% 400%',
                animation: 'gradientShift 14s ease infinite',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                p: 2,
                py: 6,
            }}
        >
            <Container maxWidth="sm">
                <Paper
                    elevation={0}
                    sx={{
                        borderRadius: 4,
                        p: { xs: 3.5, sm: 5 },
                        background: 'rgba(255,255,255,0.97)',
                        backdropFilter: 'blur(20px)',
                        boxShadow: '0 25px 80px rgba(127, 85, 57,0.4)',
                    }}
                >
                    {/* Logo */}
                    <Box sx={{ textAlign: 'center', mb: 4 }}>
                        <Box sx={{
                            width: 60, height: 60, mx: 'auto', mb: 2,
                            background: 'linear-gradient(135deg, #9c6644, #9c6644)',
                            borderRadius: 3,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: '0 8px 24px rgba(156, 102, 68,0.4)',
                        }}>
                            <AccountBalanceIcon sx={{ color: '#e6ccb2', fontSize: 30 }} />
                        </Box>
                        <Typography variant="h5" fontWeight={800} color="#7f5539">Open a Free Account</Typography>
                        <Typography variant="body2" color="#9c6644" mt={0.5}>
                            Join EagleTrust Bank today — it takes 5 minutes
                        </Typography>
                    </Box>

                    <Box>
                        <Grid container spacing={2}>

                            {/* ── PERSONAL INFO ── */}
                            <SectionLabel>Personal Information</SectionLabel>

                            <Grid item xs={12}>
                                <TextField
                                    fullWidth label="Full Name" id="reg-full-name" size="medium"
                                    {...register('fullName', {
                                        required: 'Name is required',
                                        minLength: { value: 3, message: 'Name must be at least 3 characters' },
                                        maxLength: { value: 150, message: 'Name cannot exceed 150 characters' },
                                        pattern: { value: /^[A-Za-z\s]+$/, message: 'Invalid entry — name cannot contain numbers or special characters' }
                                    })}
                                    onKeyDown={(e) => {
                                        if (/[0-9]/.test(e.key)) {
                                            e.preventDefault();
                                            toast.error('Invalid entry — name cannot contain numbers.', { toastId: 'name-err' });
                                        }
                                    }}
                                    error={!!errors.fullName} helperText={errors.fullName?.message}
                                />
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth label="Date of Birth" id="reg-dob" type="date" size="medium"
                                    InputLabelProps={{ shrink: true }}
                                    inputProps={{ max: new Date().toISOString().split('T')[0] }}
                                    {...register('dob', {
                                        required: 'Date of birth is required',
                                        validate: (value) => {
                                            const selected = new Date(value);
                                            const today = new Date();
                                            if (selected > today) return 'Date of birth cannot be in the future.';
                                            const minDate = new Date();
                                            minDate.setFullYear(minDate.getFullYear() - 120);
                                            if (selected < minDate) return 'Please enter a valid date of birth.';
                                            return true;
                                        }
                                    })}
                                    onChange={(e) => {
                                        const selectedDate = new Date(e.target.value);
                                        const today = new Date();
                                        let age = today.getFullYear() - selectedDate.getFullYear();
                                        const m = today.getMonth() - selectedDate.getMonth();
                                        if (m < 0 || (m === 0 && today.getDate() < selectedDate.getDate())) age--;
                                        if (age < 18) {
                                            toast.warn('You will be opted for a Minor Account.', { toastId: 'minor-warn' });
                                        }
                                    }}
                                    error={!!errors.dob} helperText={errors.dob?.message}
                                />
                            </Grid>

                            {/* Gender */}
                            <Grid item xs={12} sm={6}>
                                <FormControl fullWidth error={!!errors.gender}>
                                    <FormLabel id="reg-gender-label" sx={{ color: '#7f5539', fontWeight: 600, fontSize: '0.85rem', mb: 0.5 }}>
                                        Gender *
                                    </FormLabel>
                                    <Controller
                                        name="gender"
                                        control={control}
                                        rules={{ required: 'Please select a gender' }}
                                        render={({ field }) => (
                                            <RadioGroup row {...field}>
                                                {['Male', 'Female', 'Other'].map((g) => (
                                                    <FormControlLabel
                                                        key={g} value={g}
                                                        control={<Radio size="small" sx={{ color: '#9c6644', '&.Mui-checked': { color: '#7f5539' } }} />}
                                                        label={<Typography variant="body2">{g}</Typography>}
                                                    />
                                                ))}
                                            </RadioGroup>
                                        )}
                                    />
                                    {errors.gender && <FormHelperText>{errors.gender.message}</FormHelperText>}
                                </FormControl>
                            </Grid>

                            {/* Email */}
                            <Grid item xs={12}>
                                <TextField
                                    fullWidth label="Email Address" id="reg-email" type="email" size="medium"
                                    placeholder="example@email.com"
                                    {...register('email', {
                                        required: 'Email address is required',
                                        pattern: {
                                            value: /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/,
                                            message: 'Enter a valid email address (e.g. name@domain.com)'
                                        },
                                        maxLength: { value: 254, message: 'Email address is too long' }
                                    })}
                                    error={!!errors.email} helperText={errors.email?.message}
                                />
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth label="Phone Number" id="reg-phone" size="medium"
                                    inputProps={{ maxLength: 10 }}
                                    {...register('phone', {
                                        required: 'Phone number is required',
                                        pattern: { value: /^\d{10}$/, message: 'Must be exactly 10 digits' },
                                        validate: {
                                            noRepeat: (v) => !/^(\d)\1+$/.test(v) || 'Invalid — cannot be a repeating digit sequence.',
                                            noLeadingZero: (v) => v[0] !== '0' || 'Phone number cannot start with 0.',
                                            validPrefix: (v) => /^[6-9]/.test(v) || 'Enter a valid Indian mobile number (starts with 6–9).',
                                        }
                                    })}
                                    onKeyDown={(e) => {
                                        const allowedKeys = ['Backspace', 'Tab', 'ArrowLeft', 'ArrowRight', 'Delete'];
                                        if (!/[0-9]/.test(e.key) && !allowedKeys.includes(e.key)) {
                                            e.preventDefault();
                                            toast.error('Invalid entry — phone number can only contain digits.', { toastId: 'phone-err' });
                                        }
                                    }}
                                    error={!!errors.phone} helperText={errors.phone?.message}
                                />
                            </Grid>

                            {/* ── ADDRESS ── */}
                            <SectionLabel>Address Details</SectionLabel>

                            <Grid item xs={12}>
                                <TextField
                                    fullWidth label="Address" id="reg-address" size="medium" multiline rows={3}
                                    {...register('address', {
                                        required: 'Address is required',
                                        minLength: { value: 10, message: 'Minimum 10 characters required' },
                                        maxLength: { value: 500, message: 'Address cannot exceed 500 characters' }
                                    })}
                                    error={!!errors.address}
                                    helperText={
                                        errors.address?.message ||
                                        `${(watchAddress || '').length} characters${(watchAddress || '').length < 10 ? ` (${10 - (watchAddress || '').length} more needed)` : ''}`
                                    }
                                />
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <TextField
                                    select fullWidth label="City" id="reg-city" defaultValue="" size="medium"
                                    {...register('city', { required: 'Please select a city' })}
                                    error={!!errors.city} helperText={errors.city?.message}
                                >
                                    {[
                                        'Hyderabad', 'Warangal', 'Nizamabad', 'Karimnagar', 'Khammam',
                                        'Mahbubnagar', 'Nalgonda', 'Adilabad', 'Suryapet', 'Miryalaguda',
                                        'Jagtial', 'Siddipet', 'Mancherial', 'Ramagundam', 'Sangareddy'
                                    ].map((city) => (
                                        <MenuItem key={city} value={city}>{city}</MenuItem>
                                    ))}
                                </TextField>
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <Controller
                                    name="state"
                                    control={control}
                                    defaultValue="Telangana"
                                    render={({ field }) => (
                                        <TextField
                                            {...field}
                                            fullWidth label="State" id="reg-state" size="medium"
                                            InputProps={{
                                                readOnly: true,
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <LockIcon sx={{ fontSize: 18, color: '#9c6644', opacity: 0.6 }} />
                                                    </InputAdornment>
                                                ),
                                            }}
                                            sx={{ '& .MuiInputBase-input': { color: '#555', fontWeight: 500 } }}
                                        />
                                    )}
                                />
                            </Grid>

                            <Grid item xs={12}>
                                <Controller
                                    name="country"
                                    control={control}
                                    defaultValue="India"
                                    render={({ field }) => (
                                        <TextField
                                            {...field}
                                            fullWidth label="Country" id="reg-country" size="medium"
                                            InputProps={{
                                                readOnly: true,
                                                endAdornment: (
                                                    <InputAdornment position="end">
                                                        <LockIcon sx={{ fontSize: 18, color: '#9c6644', opacity: 0.6 }} />
                                                    </InputAdornment>
                                                ),
                                            }}
                                            sx={{ '& .MuiInputBase-input': { color: '#555', fontWeight: 500 } }}
                                        />
                                    )}
                                />
                            </Grid>

                            {/* ── KYC ── */}
                            <SectionLabel>KYC Details</SectionLabel>

                            {/* Aadhaar */}
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth label="Aadhaar Number" id="reg-aadhaar" size="medium"
                                    placeholder="XXXX XXXX XXXX"
                                    inputProps={{ maxLength: 12 }}
                                    InputProps={{
                                        startAdornment: (
                                            <InputAdornment position="start">
                                                <BadgeIcon sx={{ fontSize: 18, color: '#9c6644' }} />
                                            </InputAdornment>
                                        )
                                    }}
                                    {...register('aadhaar', {
                                        required: 'Aadhaar number is required',
                                        pattern: {
                                            value: /^\d{12}$/,
                                            message: 'Aadhaar must be exactly 12 digits'
                                        },
                                        validate: {
                                            noRepeat: (v) => !/^(\d)\1+$/.test(v) || 'Aadhaar cannot be all repeating digits.',
                                            noAllZeros: (v) => v !== '000000000000' || 'Invalid Aadhaar number.',
                                            validFirstDigit: (v) => /^[2-9]/.test(v) || 'Aadhaar must start with a digit between 2–9.',
                                        }
                                    })}
                                    onKeyDown={(e) => {
                                        const allowedKeys = ['Backspace', 'Tab', 'ArrowLeft', 'ArrowRight', 'Delete'];
                                        if (!/[0-9]/.test(e.key) && !allowedKeys.includes(e.key)) {
                                            e.preventDefault();
                                            toast.error('Aadhaar can only contain digits.', { toastId: 'aadhaar-key-err' });
                                        }
                                    }}
                                    error={!!errors.aadhaar}
                                    helperText={errors.aadhaar?.message || `${(watchAadhaar || '').length}/12 digits`}
                                />
                            </Grid>

                            {/* PAN */}
                            <Grid item xs={12} sm={6}>
                                <TextField
                                    fullWidth label="PAN Number" id="reg-pan" size="medium"
                                    placeholder="ABCDE1234F"
                                    inputProps={{ maxLength: 10, style: { textTransform: 'uppercase' } }}
                                    InputProps={{
                                        startAdornment: (
                                            <InputAdornment position="start">
                                                <CreditCardIcon sx={{ fontSize: 18, color: '#9c6644' }} />
                                            </InputAdornment>
                                        )
                                    }}
                                    {...register('pan', {
                                        required: 'PAN number is required',
                                        pattern: {
                                            value: /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/,
                                            message: 'Invalid PAN — format must be ABCDE1234F'
                                        }
                                    })}
                                    onChange={(e) => {
                                        e.target.value = e.target.value.toUpperCase();
                                    }}
                                    onKeyDown={(e) => {
                                        const val = watch('pan') || '';
                                        const pos = e.target.selectionStart;
                                        // First 5 chars → letters only; next 4 → digits; last 1 → letter
                                        const letterPositions = [0,1,2,3,4,9];
                                        const digitPositions = [5,6,7,8];
                                        const allowedKeys = ['Backspace', 'Tab', 'ArrowLeft', 'ArrowRight', 'Delete'];
                                        if (allowedKeys.includes(e.key)) return;
                                        if (letterPositions.includes(pos) && !/[A-Za-z]/.test(e.key)) {
                                            e.preventDefault();
                                            toast.error(`Position ${pos + 1} of PAN must be a letter.`, { toastId: 'pan-letter-err' });
                                        } else if (digitPositions.includes(pos) && !/[0-9]/.test(e.key)) {
                                            e.preventDefault();
                                            toast.error(`Position ${pos + 1} of PAN must be a digit.`, { toastId: 'pan-digit-err' });
                                        }
                                    }}
                                    error={!!errors.pan}
                                    helperText={errors.pan?.message || `${(watchPan || '').length}/10 characters`}
                                />
                            </Grid>

                            {/* ── ACCOUNT ── */}
                            <SectionLabel>Account Preferences</SectionLabel>

                            <Grid item xs={12}>
                                <FormControl error={!!errors.accountType} component="fieldset">
                                    <FormLabel id="reg-account-type-label" sx={{ color: '#7f5539', fontWeight: 600 }}>
                                        Account Type *
                                    </FormLabel>
                                    <Controller
                                        name="accountType"
                                        control={control}
                                        rules={{ required: 'Please select an account type' }}
                                        render={({ field }) => (
                                            <RadioGroup row {...field}>
                                                <FormControlLabel
                                                    value="Savings Account"
                                                    control={<Radio sx={{ color: '#9c6644', '&.Mui-checked': { color: '#7f5539' } }} />}
                                                    label="Savings Account"
                                                />
                                                <FormControlLabel
                                                    value="Current Account"
                                                    control={<Radio sx={{ color: '#9c6644', '&.Mui-checked': { color: '#7f5539' } }} />}
                                                    label="Current Account"
                                                />
                                            </RadioGroup>
                                        )}
                                    />
                                    {errors.accountType && (
                                        <FormHelperText>{errors.accountType.message}</FormHelperText>
                                    )}
                                </FormControl>
                            </Grid>
                        </Grid>

                        <Button
                            onClick={handleSubmit((data) => {
                                const selectedDate = new Date(data.dob);
                                const today = new Date();
                                let age = today.getFullYear() - selectedDate.getFullYear();
                                const m = today.getMonth() - selectedDate.getMonth();
                                if (m < 0 || (m === 0 && today.getDate() < selectedDate.getDate())) age--;
                                data.isMinor = age < 18;

                                // Normalize PAN to uppercase before submit
                                if (data.pan) data.pan = data.pan.toUpperCase();

                                // Double-check phone repeating sequence (belt-and-suspenders)
                                if (/^(\d)\1+$/.test(data.phone)) {
                                    toast.error('Invalid phone number — cannot be a repeating digit sequence.', { toastId: 'phone-repeat-err' });
                                    return;
                                }

                                setFormData(data);
                                setShowConfirmModal(true);
                            })}
                            fullWidth
                            variant="contained"
                            id="reg-submit-btn"
                            size="large"
                            sx={{
                                mt: 3,
                                background: 'linear-gradient(135deg, #7f5539, #9c6644)',
                                color: '#e6ccb2',
                                fontWeight: 700,
                                py: 1.4,
                                '&:hover': { background: 'linear-gradient(135deg, #7f5539, #7f5539)' },
                            }}
                        >
                            Review & Register
                        </Button>
                        <Typography variant="body2" sx={{ textAlign: 'center', mt: 2.5, color: '#9c6644' }}>
                            Already have an account?{' '}
                            <Link component={RouterLink} to="/login" fontWeight={600} color="#7f5539" underline="hover">
                                Login
                            </Link>
                        </Typography>
                        <Typography variant="caption" display="block" textAlign="center" color="#9c6644" mt={2}>
                            By proceeding, you agree to our Terms of Use, Privacy Policy and consent under RBI KYC norms.
                        </Typography>
                    </Box>
                </Paper>

                <Typography variant="caption" sx={{ display: 'block', textAlign: 'center', mt: 3, color: 'rgba(255,255,255,0.4)' }}>
                    🔒 256-bit SSL Encrypted | RBI Licensed | DICGC Insured
                </Typography>
            </Container>

            {/* Pre-Submit Confirmation Modal */}
            <Dialog
                open={showConfirmModal}
                onClose={() => setShowConfirmModal(false)}
                PaperProps={{ sx: { borderRadius: 3, p: 1 } }}
            >
                <DialogTitle fontWeight={700} color="#7f5539">
                    Confirm Registration Details
                </DialogTitle>
                <DialogContent>
                    <DialogContentText color="#9c6644" mb={2}>
                        Please review your details carefully before submitting. This information will be used to create your bank account.
                    </DialogContentText>
                    {formData && (
                        <Box sx={{ bgcolor: 'rgba(156, 102, 68, 0.05)', p: 2, borderRadius: 2 }}>
                            {[
                                ['Name', formData.fullName],
                                ['DOB', formData.dob],
                                ['Gender', formData.gender],
                                ['Email', formData.email],
                                ['Phone', formData.phone],
                                ['Address', formData.address],
                                ['City', formData.city],
                                ['State', formData.state],
                                ['Aadhaar', `XXXX XXXX ${formData.aadhaar?.slice(-4)}`],
                                ['PAN', formData.pan],
                                ['Account Type', formData.accountType],
                            ].map(([label, value]) => (
                                <Typography key={label} variant="body2" mb={0.5}>
                                    <b>{label}:</b> {value}
                                </Typography>
                            ))}
                        </Box>
                    )}
                </DialogContent>
                <DialogActions sx={{ px: 3, pb: 2 }}>
                    <Button onClick={() => setShowConfirmModal(false)} color="inherit" sx={{ fontWeight: 600 }}>
                        Cancel
                    </Button>
                    <Button
                        onClick={handleConfirmSubmit}
                        variant="contained"
                        disabled={isLoading}
                        sx={{ background: '#7f5539', '&:hover': { background: '#9c6644' }, fontWeight: 600, minWidth: 160 }}
                        startIcon={isLoading ? <CircularProgress size={16} color="inherit" /> : null}
                    >
                        {isLoading ? 'Submitting...' : 'Confirm & Proceed'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    );
}