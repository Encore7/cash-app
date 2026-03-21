import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
    Box,
    Button,
    Card,
    CardContent,
    Chip,
    CircularProgress,
    Collapse,
    Grid,
    IconButton,
    Paper,
    Tab,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    Typography,
} from '@mui/material'
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown'
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp'
import { PieChart } from '@mui/x-charts/PieChart'

const API = 'http://localhost:8000'

// ─── types ───────────────────────────────────────────────────────────────────

interface TenantSummary {
    id: string
    code: string
    name: string
    is_active: boolean
    matched: number
    unmatched: number
    manual_review: number
    total: number
}

interface Summary {
    matched: number
    unmatched: number
    manual_review: number
    total: number
    tenants: TenantSummary[]
}

interface Match {
    id: string
    run_id: string
    status: string
    confidence_score: number
    match_rule: string
    amount_applied: number | null
    variance_amount: number | null
    notes: string | null
    source: string
    is_selected: boolean
    created_at: string | null
    bank_booking_date: string | null
    bank_amount: number | null
    bank_currency: string | null
    bank_counterparty: string | null
    bank_reference: string | null
    bank_payment_purpose: string | null
    remittance_invoice_number: string | null
    remittance_paid_amount: number | null
    remittance_currency: string | null
    remittance_customer_reference: string | null
}

interface BankStatement {
    id: string
    line_number: number
    booking_date: string
    value_date: string | null
    amount: number
    currency: string
    counterparty_name: string | null
    payment_purpose: string | null
    bank_reference: string | null
    customer_reference: string | null
}

interface RemittanceLine {
    id: string
    line_number: number
    invoice_number: string | null
    invoice_date: string | null
    paid_amount: number | null
    currency: string | null
    customer_reference: string | null
    raw_line_text: string
}

interface RemittanceHeader {
    id: string
    advice_number: string | null
    advice_date: string | null
    payer_name: string | null
    document_currency: string | null
    total_paid_amount: number | null
    lines: RemittanceLine[]
}

// ─── helpers ──────────────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, 'success' | 'error' | 'warning' | 'default'> = {
    AUTO_MATCHED: 'success',
    APPROVED: 'success',
    CLOSED: 'success',
    UNMATCHED: 'error',
    MANUAL_REVIEW: 'warning',
    PARTIAL_MATCH: 'warning',
    REJECTED: 'error',
}

function fmt(n: number | null | undefined, currency?: string | null) {
    if (n == null) return '–'
    const s = n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    return currency ? `${currency} ${s}` : s
}

// ─── Remittance expandable row ────────────────────────────────────────────────

function RemittanceRow({ header }: { header: RemittanceHeader }) {
    const [open, setOpen] = useState(true)
    return (
        <>
            <TableRow>
                <TableCell>
                    <IconButton size="small" onClick={() => setOpen(!open)}>
                        {open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
                    </IconButton>
                </TableCell>
                <TableCell>{header.advice_number ?? '–'}</TableCell>
                <TableCell>{header.advice_date ?? '–'}</TableCell>
                <TableCell>{header.payer_name ?? '–'}</TableCell>
                <TableCell>{fmt(header.total_paid_amount, header.document_currency)}</TableCell>
                <TableCell>{header.lines.length}</TableCell>
            </TableRow>
            <TableRow>
                <TableCell colSpan={6} sx={{ py: 0 }}>
                    <Collapse in={open} unmountOnExit>
                        <Box sx={{ m: 1 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                Lines
                            </Typography>
                            <Table size="small">
                                <TableHead>
                                    <TableRow>
                                        <TableCell>#</TableCell>
                                        <TableCell>Invoice</TableCell>
                                        <TableCell>Invoice Date</TableCell>
                                        <TableCell>Paid Amount</TableCell>
                                        <TableCell>Ccy</TableCell>
                                        <TableCell>Customer Ref</TableCell>
                                        <TableCell>Raw Text</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {header.lines.map((ln) => (
                                        <TableRow key={ln.id}>
                                            <TableCell>{ln.line_number}</TableCell>
                                            <TableCell>{ln.invoice_number ?? '–'}</TableCell>
                                            <TableCell>{ln.invoice_date ?? '–'}</TableCell>
                                            <TableCell>{fmt(ln.paid_amount)}</TableCell>
                                            <TableCell>{ln.currency ?? '–'}</TableCell>
                                            <TableCell>{ln.customer_reference ?? '–'}</TableCell>
                                            <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {ln.raw_line_text}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </Box>
                    </Collapse>
                </TableCell>
            </TableRow>
        </>
    )
}

// ─── main component ───────────────────────────────────────────────────────────

export default function AnalyticsPage() {
    const [summary, setSummary] = useState<Summary | null>(null)
    const [matches, setMatches] = useState<Match[]>([])
    const [bankStmts, setBankStmts] = useState<BankStatement[]>([])
    const [remHeaders, setRemHeaders] = useState<RemittanceHeader[]>([])
    const [matchFilter, setMatchFilter] = useState<string | null>(null)
    const [tab, setTab] = useState(0)
    const [loading, setLoading] = useState(true)
    const [actionLoading, setActionLoading] = useState<string | null>(null)

    const loadData = () => {
        return Promise.all([
            axios.get<Summary>(`${API}/analytics/summary`),
            axios.get<Match[]>(`${API}/analytics/matches`),
            axios.get<BankStatement[]>(`${API}/analytics/bank-statements`),
            axios.get<RemittanceHeader[]>(`${API}/analytics/remittance-headers`),
        ]).then(([s, m, b, r]) => {
            setSummary(s.data)
            setMatches(m.data)
            setBankStmts(b.data)
            setRemHeaders(r.data)
        })
    }

    useEffect(() => {
        loadData().finally(() => setLoading(false))
    }, [])

    const handleMarkMatched = async (id: string) => {
        setActionLoading(id)
        try {
            await axios.post(`${API}/analytics/matches/${id}/mark-matched`)
            await loadData()
        } finally {
            setActionLoading(null)
        }
    }

    const handleMarkUnmatched = async (id: string) => {
        setActionLoading(id)
        try {
            await axios.post(`${API}/analytics/matches/${id}/mark-unmatched`)
            await loadData()
        } finally {
            setActionLoading(null)
        }
    }

    const pieData = summary
        ? [
            { id: 0, value: summary.matched, label: 'Matched', color: '#4caf50' },
            { id: 1, value: summary.unmatched, label: 'Unmatched', color: '#f44336' },
            { id: 2, value: summary.manual_review, label: 'Manual Review', color: '#ff9800' },
        ]
        : []

    const filteredMatches = matchFilter
        ? matches.filter((m) => {
            if (matchFilter === 'matched') return ['AUTO_MATCHED', 'APPROVED', 'CLOSED'].includes(m.status)
            if (matchFilter === 'unmatched') return m.status === 'UNMATCHED'
            if (matchFilter === 'manual_review') return ['MANUAL_REVIEW', 'PARTIAL_MATCH', 'REJECTED'].includes(m.status)
            return true
        })
        : matches

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
                Reconciliation Analytics
            </Typography>

            {/* ── Pie Charts ─────────────────────────────────────────────────────── */}
            <Grid container spacing={3} sx={{ mb: 3 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card>
                        <CardContent>
                            <Typography variant="h6" gutterBottom>
                                Overall Match Status
                            </Typography>
                            {summary && summary.total > 0 ? (
                                <PieChart
                                    series={[
                                        {
                                            data: pieData,
                                            highlightScope: { faded: 'global', highlighted: 'item' },
                                            innerRadius: 40,
                                        },
                                    ]}
                                    onItemClick={(_e, item) => {
                                        const keys = ['matched', 'unmatched', 'manual_review']
                                        const clicked = keys[item.dataIndex]
                                        setMatchFilter((prev) => (prev === clicked ? null : clicked))
                                    }}
                                    height={280}
                                    slotProps={{ legend: { direction: 'row', position: { vertical: 'bottom', horizontal: 'middle' } } }}
                                />
                            ) : (
                                <Typography color="text.secondary">No match data yet.</Typography>
                            )}
                            {matchFilter && (
                                <Typography variant="caption" color="primary">
                                    Showing <strong>{matchFilter.replace('_', ' ')}</strong> matches below — click again to clear
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* ── Tenant breakdown cards ────────────────────────────────────────── */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Typography variant="h6" gutterBottom>
                        Tenant Breakdown
                    </Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                        {summary?.tenants.map((t) => (
                            <Card key={t.id} variant="outlined">
                                <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                                    <Box display="flex" justifyContent="space-between" alignItems="center">
                                        <Box>
                                            <Typography variant="subtitle1">{t.name}</Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                {t.code} · {t.is_active ? 'Active' : 'Inactive'}
                                            </Typography>
                                        </Box>
                                        <Box display="flex" gap={1}>
                                            <Chip size="small" label={`✓ ${t.matched}`} color="success" variant="outlined" />
                                            <Chip size="small" label={`✗ ${t.unmatched}`} color="error" variant="outlined" />
                                            <Chip size="small" label={`~ ${t.manual_review}`} color="warning" variant="outlined" />
                                        </Box>
                                    </Box>
                                </CardContent>
                            </Card>
                        ))}
                        {!summary?.tenants.length && (
                            <Typography color="text.secondary">No tenants found.</Typography>
                        )}
                    </Box>
                </Grid>
            </Grid>

            {/* ── Reconciliation Matches table ────────────────────────────────────── */}
            <Typography variant="h6" gutterBottom>
                Reconciliation Matches {matchFilter ? `(${matchFilter.replace('_', ' ')})` : '(all)'}
            </Typography>
            <TableContainer component={Paper} sx={{ mb: 4 }}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>Status</TableCell>
                            <TableCell>Rule</TableCell>
                            <TableCell>Confidence</TableCell>
                            <TableCell>Bank Date</TableCell>
                            <TableCell>Bank Amount</TableCell>
                            <TableCell>Counterparty</TableCell>
                            <TableCell>Bank Ref</TableCell>
                            <TableCell>Invoice #</TableCell>
                            <TableCell>Rem. Amount</TableCell>
                            <TableCell>Variance</TableCell>
                            <TableCell>Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {filteredMatches.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={11} align="center">
                                    <Typography color="text.secondary">No records found.</Typography>
                                </TableCell>
                            </TableRow>
                        )}
                        {filteredMatches.map((m) => (
                            <TableRow key={m.id} hover>
                                <TableCell>
                                    <Chip
                                        size="small"
                                        label={m.status}
                                        color={STATUS_COLORS[m.status] ?? 'default'}
                                    />
                                </TableCell>
                                <TableCell>{m.match_rule}</TableCell>
                                <TableCell>{(m.confidence_score * 100).toFixed(1)}%</TableCell>
                                <TableCell>{m.bank_booking_date ?? '–'}</TableCell>
                                <TableCell>{fmt(m.bank_amount, m.bank_currency)}</TableCell>
                                <TableCell>{m.bank_counterparty ?? '–'}</TableCell>
                                <TableCell>{m.bank_reference ?? '–'}</TableCell>
                                <TableCell>{m.remittance_invoice_number ?? '–'}</TableCell>
                                <TableCell>{fmt(m.remittance_paid_amount, m.remittance_currency)}</TableCell>
                                <TableCell>{fmt(m.variance_amount)}</TableCell>
                                <TableCell>
                                    <Box display="flex" gap={0.5}>
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            color="success"
                                            disabled={actionLoading === m.id || m.status === 'APPROVED'}
                                            onClick={() => handleMarkMatched(m.id)}
                                        >
                                            {actionLoading === m.id ? <CircularProgress size={14} /> : 'Match'}
                                        </Button>
                                        <Button
                                            size="small"
                                            variant="outlined"
                                            color="error"
                                            disabled={actionLoading === m.id || m.status === 'UNMATCHED'}
                                            onClick={() => handleMarkUnmatched(m.id)}
                                        >
                                            Unmatch
                                        </Button>
                                    </Box>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </TableContainer>

            {/* ── Evidence Tabs ────────────────────────────────────────────────────── */}
            <Typography variant="h6" gutterBottom>
                Matching Evidence
            </Typography>
            <Paper>
                <Tabs value={tab} onChange={(_e, v) => setTab(v)}>
                    <Tab label="Bank Statement" />
                    <Tab label="Remittance Advice Headers" />
                </Tabs>

                {/* Bank Statement tab */}
                {tab === 0 && (
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell>#</TableCell>
                                    <TableCell>Booking Date</TableCell>
                                    <TableCell>Value Date</TableCell>
                                    <TableCell>Amount</TableCell>
                                    <TableCell>Ccy</TableCell>
                                    <TableCell>Counterparty</TableCell>
                                    <TableCell>Bank Ref</TableCell>
                                    <TableCell>Customer Ref</TableCell>
                                    <TableCell>Purpose</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {bankStmts.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={9} align="center">
                                            <Typography color="text.secondary">No bank statement rows.</Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                                {bankStmts.map((b) => (
                                    <TableRow key={b.id} hover>
                                        <TableCell>{b.line_number}</TableCell>
                                        <TableCell>{b.booking_date}</TableCell>
                                        <TableCell>{b.value_date ?? '–'}</TableCell>
                                        <TableCell>{fmt(b.amount)}</TableCell>
                                        <TableCell>{b.currency}</TableCell>
                                        <TableCell>{b.counterparty_name ?? '–'}</TableCell>
                                        <TableCell>{b.bank_reference ?? '–'}</TableCell>
                                        <TableCell>{b.customer_reference ?? '–'}</TableCell>
                                        <TableCell sx={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                            {b.payment_purpose ?? '–'}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}

                {/* Remittance Advice Headers tab */}
                {tab === 1 && (
                    <TableContainer>
                        <Table size="small">
                            <TableHead>
                                <TableRow>
                                    <TableCell />
                                    <TableCell>Advice #</TableCell>
                                    <TableCell>Date</TableCell>
                                    <TableCell>Payer</TableCell>
                                    <TableCell>Total Paid</TableCell>
                                    <TableCell>Lines</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {remHeaders.length === 0 && (
                                    <TableRow>
                                        <TableCell colSpan={6} align="center">
                                            <Typography color="text.secondary">No remittance headers.</Typography>
                                        </TableCell>
                                    </TableRow>
                                )}
                                {remHeaders.map((h) => (
                                    <RemittanceRow key={h.id} header={h} />
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
            </Paper>
        </Box>
    )
}
