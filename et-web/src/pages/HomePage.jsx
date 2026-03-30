import Navbar from '../components/Navbar';
import HeroSection from '../components/HeroSection';
import ServicesSection from '../components/ServicesSection';
import FraudCarousel from '../components/FraudCarousel';
import QuickLinksSection from '../components/QuickLinksSection';
import VideosSection from '../components/VideosSection';
import Footer from '../components/Footer';
import { Box } from '@mui/material';

export default function HomePage() {
    return (
        <Box>
            <Navbar />
            <main>
                <HeroSection />
                <ServicesSection />
                <FraudCarousel />
                <QuickLinksSection />
                <VideosSection />
            </main>
            <Footer />
        </Box>
    );
}
