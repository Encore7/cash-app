import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
    Box,
    Chip,
    CircularProgress,
    Paper,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
} from '@mui/material'

const API = 'http://localhost:8000'

interface JournalEntry {
    id: string
    run_id: string
    line_number: number
    company_code: string
    posting_date: string
    document_date: string
    document_type: string
    gl_account: string
    debit: number | null
    credit: number | null
    currency: string
    item_text: string | null
    source_file_name: string | null
    created_at: string | null
    reconciliation_match_id: string | null
    bank_statement_id: string | null
    remittance_advice_line_id: string | null
}

function fmt(n: number | null | undefined, currency?: string | null) {
    if (n == null) return '–'
    const s = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return currency ? `${currency} ${s}` : s
}

export default function JournalPage() {
    const [entries, setEntries] = useState<JournalEntry[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        axios
            .get<JournalEntry[]>(`${API}/analytics/journal-entries`)
            .then((r) => setEntries(r.data))
            .finally(() => setLoading(false))
    }, [])

    if (loading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
                <CircularProgress />
            </Box>
        )
    }

    return (
        <Box sx={{ p: 3 }}>
            <Typography variant="h5" gutterBottom>
                Journal Entries
            </Typography>
            <TableContainer component={Paper}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>#</TableCell>
                            <TableCell>Company</TableCell>
                            <TableCell>Posting Date</TableCell>
                            <TableCell>Doc Date</TableCell>
                            <TableCell>Doc Type</TableCell>
                            <TableCell>GL Account</TableCell>
                            <TableCell align="right">Debit</TableCell>
                            <TableCell align="right">Credit</TableCell>
                            <TableCell>Ccy</TableCell>
                            <TableCell>Item Text</TableCell>
                            <TableCell>Source File</TableCell>
                            <TableCell>Links</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {entries.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={12} align="center">
                                    <Typography color="text.secondary">No journal entries yet.</Typography>
                                </TableCell>
                            </TableRow>
                        )}
                        {entries.map((e) => (
                            <TableRow key={e.id} hover>
                                <TableCell>{e.line_number}</TableCell>
                                <TableCell>{e.company_code}</TableCell>
                                <TableCell>{e.posting_date}</TableCell>
                                <TableCell>{e.document_date}</TableCell>
                                <TableCell>{e.document_type}</TableCell>
                                <TableCell>{e.gl_account}</TableCell>
                                <TableCell align="right">{fmt(e.debit)}</TableCell>
                                <TableCell align="right">{fmt(e.credit)}</TableCell>
                                <TableCell>{e.currency}</TableCell>
                                <TableCell
                                    sx={{
                                        maxWidth: 200,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {e.item_text ?? '–'}
                                </TableCell>
                                <TableCell
                                    sx={{
                                        maxWidth: 160,
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        whiteSpace: 'nowrap',
                                    }}
                                >
                                    {e.source_file_name ?? '–'}
                                </TableCell>
                                <TableCell>
                                    <Box display="flex" gap={0.5} flexWrap="wrap">
                                        {e.reconciliation_match_id && (
                                            <Chip size="small" label="Match" color="success" variant="outlined" />
                                        )}
                                        {e.bank_statement_id && (
                                            <Chip size="small" label="Bank" color="primary" variant="outlined" />
                                        )}
                                        {e.remittance_advice_line_id && (
                                            <Chip size="small" label="Rem." color="secondary" variant="outlined" />
                                        )}
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>
        </Box>
    )
}
