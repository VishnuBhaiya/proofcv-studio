import { Sparkles } from 'lucide-react';

// Navigation placeholder only. The working local Portfolio Studio is not published.
export default function PortfolioWebsite() {
    return <section className="page-content" aria-labelledby="portfolio-studio-title">
        <div className="page-heading"><div><h2 id="portfolio-studio-title">Portfolio Studio</h2><p>Your confirmed CV. Your professional website.</p></div></div>
        <div className="empty-state"><Sparkles size={36} aria-hidden="true"/><h3>Coming soon.</h3><p>The full Portfolio Studio is being developed separately by Vishnu. Website generation, 3D scenes and publishing are not enabled in this shared version.</p><p>Your confirmed profile and saved CVs remain available in the other sections.</p></div>
    </section>;
}
