// Legacy profiles store education as text, sometimes with comma-separated degrees.
// Split only before a qualification, not before an institution or a date.
export function splitEducationEntries(value: string): string[] {
    return value.split(/\n\s*\n/).flatMap(block => {
        // Keep labelled form records together, including empty input values.
        if (block.startsWith('Degree:')) return [block];
        return block.split(/(?:[,;]\s*|\n+)(?=(?:Bachelor(?:'s)?|Master(?:'s)?|Doctor(?:ate)?|Ph\.?D\.?|Diploma|Certificate|Associate)\b)/i)
            .map(entry => entry.trim());
    }).filter(entry => entry.trim().length > 0);
}

export function educationEntries(value: string) {
    return splitEducationEntries(value).map(entry => {
            const date = entry.match(/\s*\(?((?:Expected|Estimated)(?: graduation| completion| end of)?[^()\n]*?\b(?:19|20)\d{2}(?: academic year)?\.?)\)?\s*$/i);
            const body = date ? entry.slice(0, date.index).trim().replace(/[.,;]$/, '') : entry;
            const institution = body.search(/,\s*(?:University|College|Institute|TAFE)\b/i);
            return { degree: institution >= 0 ? body.slice(0, institution) : body,
                institution: institution >= 0 ? body.slice(institution + 1).trim() : '',
                date: date?.[1] || '' };
        });
}
