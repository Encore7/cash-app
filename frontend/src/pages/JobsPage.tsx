import React, { useEffect, useRef, useState } from 'react'
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Chip,
    CircularProgress,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    LinearProgress,
    ListItemText,
    MenuItem,
    OutlinedInput,
    Select,
    Stack,
    Switch,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

const api = axios.create({
    baseURL: API_BASE,
})

const WS_BASE = API_BASE.replace(/^http/, 'ws')

const DAYS_OF_WEEK = [
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
]

const ALL_TENANTS_SENTINEL = '__all__'

const EMPTY_FORM = {
    tenant_ids: [] as string[],
    rule_type: 'processing',
    frequency: 'daily',
    day_of_week: 0,
    day_of_month: 1,
    run_time: '09:00',
    is_active: true,
}

interface JobProgress {
    percent: number
    step: string
    status: 'running' | 'done' | 'error'
    message?: string
    processed?: number
}

export default function JobsPage() {
    const [rules, setRules] = useState<any[]>([])
    const [tenants, setTenants] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [successMsg, setSuccessMsg] = useState('')
    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingRule, setEditingRule] = useState<any>(null)
    const [form, setForm] = useState(EMPTY_FORM)
    const [jobProgress, setJobProgress] = useState<Record<string, JobProgress>>({})
    const wsRefs = useRef<Record<string, WebSocket>>({})
    // Always holds the latest jobProgress so the cleanup closure isn't stale
    const jobProgressRef = useRef<Record<string, JobProgress>>({})
    // Track mount state to avoid calling openWs after the component is gone
    const mountedRef = useRef(true)

    useEffect(() => {
        jobProgressRef.current = jobProgress
    }, [jobProgress])

    useEffect(() => {
        mountedRef.current = true
        fetchRules()
        fetchTenants()
        // Restore any jobs that were running when the user navigated away
        const saved = sessionStorage.getItem('runningJobIds')
        const savedProgress = sessionStorage.getItem('runningJobProgress')
        if (saved) {
            sessionStorage.removeItem('runningJobIds')
            sessionStorage.removeItem('runningJobProgress')
            const ids: string[] = JSON.parse(saved)
            const prevState: Record<string, JobProgress> = savedProgress ? JSON.parse(savedProgress) : {}
            ids.forEach(id => {
                // Restore last-known progress (keeps the % visible while WS reconnects)
                const lastKnown = prevState[id] ?? { percent: 0, step: 'Reconnecting…', status: 'running' as const }
                setJobProgress(prev => ({ ...prev, [id]: { ...lastKnown, step: lastKnown.step || 'Reconnecting…' } }))
                openWs(id)
            })
        }
        return () => {
            // Save running jobs + their last-known progress so we can restore on re-mount
            const runningEntries = Object.entries(jobProgressRef.current)
                .filter(([, jp]) => jp.status === 'running')
            if (runningEntries.length > 0) {
                const ids = runningEntries.map(([id]) => id)
                const state: Record<string, JobProgress> = Object.fromEntries(runningEntries)
                sessionStorage.setItem('runningJobIds', JSON.stringify(ids))
                sessionStorage.setItem('runningJobProgress', JSON.stringify(state))
            }
            // Close all sockets – they'll be reopened on next mount
            Object.values(wsRefs.current).forEach(ws => { try { ws.close() } catch { /* ignore */ } })
            wsRefs.current = {}
            mountedRef.current = false
        }
    }, [])

    async function fetchRules() {
        setLoading(true)
        try {
            const { data } = await api.get('/jobs/rules')
            setRules(data)
        } catch (e: any) {
            setError(e?.response?.data?.detail || e.message)
        } finally {
            setLoading(false)
        }
    }

    async function fetchTenants() {
        try {
            const { data } = await api.get('/jobs/tenants')
            setTenants(data)
        } catch {
            // ignore
        }
    }

    function openCreate() {
        setEditingRule(null)
        setForm(EMPTY_FORM)
        setDialogOpen(true)
    }

    function openEdit(rule: any) {
        setEditingRule(rule)
        setForm({
            tenant_ids: (rule.tenants ?? []).map((t: any) => t.id),
            rule_type: rule.rule_type ?? 'processing',
            frequency: rule.frequency,
            day_of_week: rule.day_of_week ?? 0,
            day_of_month: rule.day_of_month ?? 1,
            run_time: rule.run_time,
            is_active: rule.is_active,
        })
        setDialogOpen(true)
    }

    function handleTenantChange(newValue: string[]) {
        const allSelected = newValue.includes(ALL_TENANTS_SENTINEL)
        const wasAllTenants = form.tenant_ids.length === 0
        if (allSelected && wasAllTenants) {
            setForm({ ...form, tenant_ids: newValue.filter(v => v !== ALL_TENANTS_SENTINEL) })
        } else if (allSelected && !wasAllTenants) {
            setForm({ ...form, tenant_ids: [] })
        } else {
            setForm({ ...form, tenant_ids: newValue.filter(v => v !== ALL_TENANTS_SENTINEL) })
        }
    }

    async function saveRule() {
        const payload = {
            tenant_ids: form.tenant_ids,
            rule_type: form.rule_type,
            frequency: form.frequency,
            day_of_week: form.frequency === 'weekly' ? form.day_of_week : null,
            day_of_month: form.frequency === 'monthly' ? form.day_of_month : null,
            run_time: form.run_time,
            is_active: form.is_active,
        }
        try {
            if (editingRule) {
                await api.patch(`/jobs/rules/${editingRule.id}`, payload)
                setSuccessMsg('Rule updated successfully')
            } else {
                await api.post('/jobs/rules', payload)
                setSuccessMsg('Rule created')
            }
            setDialogOpen(false)
            fetchRules()
        } catch (e: any) {
            setError(e?.response?.data?.detail || e.message)
        }
    }

    async function deleteRule(id: string) {
        try {
            await api.delete(`/jobs/rules/${id}`)
            setSuccessMsg('Rule deleted')
            fetchRules()
        } catch (e: any) {
            setError(e?.response?.data?.detail || e.message)
        }
    }

    async function triggerRule(id: string) {
        setError('')
        setSuccessMsg('')

        setJobProgress(prev => ({
            ...prev,
            [id]: { percent: 0, step: 'Starting…', status: 'running' },
        }))

        try {
            await api.post(`/jobs/rules/${id}/trigger`)
        } catch (e: any) {
            setJobProgress(prev => ({
                ...prev,
                [id]: { percent: 0, step: '', status: 'error', message: e?.response?.data?.detail || e.message },
            }))
            return
        }

        // Don't open a WS if the component was unmounted while the POST was in flight
        if (!mountedRef.current) return
        openWs(id)
    }

    function openWs(id: string) {
        if (wsRefs.current[id]) {
            wsRefs.current[id].close()
            delete wsRefs.current[id]
        }

        const ws = new WebSocket(`${WS_BASE}/jobs/ws/${id}`)
        wsRefs.current[id] = ws

        ws.onmessage = (evt) => {
            try {
                const msg = JSON.parse(evt.data)
                if (msg.type === 'progress') {
                    setJobProgress(prev => ({
                        ...prev,
                        [id]: { percent: msg.percent, step: msg.step, status: 'running' },
                    }))
                } else if (msg.type === 'done') {
                    setJobProgress(prev => ({
                        ...prev,
                        [id]: { percent: 100, step: 'Completed', status: 'done', processed: msg.processed },
                    }))
                    fetchRules()
                } else if (msg.type === 'error') {
                    // "No active job" means the job finished while we were on another page
                    if (msg.message?.includes('No active job')) {
                        setJobProgress(prev => { const c = { ...prev }; delete c[id]; return c })
                        fetchRules()
                    } else {
                        setJobProgress(prev => ({
                            ...prev,
                            [id]: { percent: 0, step: '', status: 'error', message: msg.message },
                        }))
                    }
                }
            } catch { /* ignore */ }
        }

        ws.onerror = () => {
            setJobProgress(prev => ({
                ...prev,
                [id]: { percent: 0, step: '', status: 'error', message: 'WebSocket connection failed' },
            }))
        }
    }

    function dismissProgress(id: string) {
        if (wsRefs.current[id]) {
            wsRefs.current[id].close()
            delete wsRefs.current[id]
        }
        setJobProgress(prev => {
            const copy = { ...prev }
            delete copy[id]
            return copy
        })
    }

    function frequencyLabel(freq: string) {
        if (freq === 'daily') return 'Daily'
        if (freq === 'weekly') return 'Weekly'
        if (freq === 'monthly') return 'Monthly'
        return freq
    }

    function scheduleDetail(rule: any) {
        if (rule.frequency === 'weekly' && rule.day_of_week != null)
            return DAYS_OF_WEEK[rule.day_of_week]
        if (rule.frequency === 'monthly' && rule.day_of_month != null)
            return `Day ${rule.day_of_month}`
        return '—'
    }

    const selectValue = form.tenant_ids.length === 0 ? [ALL_TENANTS_SENTINEL] : form.tenant_ids

    // ── DataGrid column definitions ─────────────────────────────────────────
    const columns: GridColDef[] = [
        {
            field: 'rule_type',
            headerName: 'Rule Type',
            width: 130,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value === 'matching' ? 'Matching' : 'Processing'}
                    size="small"
                    color={params.value === 'matching' ? 'secondary' : 'info'}
                />
            ),
        },
        {
            field: 'tenants',
            headerName: 'Tenants',
            flex: 1,
            minWidth: 160,
            renderCell: (params: GridRenderCellParams) => {
                const list: any[] = params.value ?? []
                return list.length > 0 ? (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, py: 0.5 }}>
                        {list.map((t: any) => (
                            <Chip key={t.id} label={t.name} size="small" variant="outlined" />
                        ))}
                    </Box>
                ) : (
                    <Chip label="All Tenants" size="small" color="default" />
                )
            },
        },
        {
            field: 'frequency',
            headerName: 'Frequency',
            width: 120,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={frequencyLabel(params.value)}
                    size="small"
                    color={params.value === 'daily' ? 'primary' : params.value === 'weekly' ? 'secondary' : 'default'}
                />
            ),
        },
        {
            field: '_schedule_detail',
            headerName: 'Day / Date',
            width: 110,
            valueGetter: (_value: any, row: any) => scheduleDetail(row),
        },
        { field: 'run_time', headerName: 'Time (UTC)', width: 110 },
        {
            field: 'is_active',
            headerName: 'Status',
            width: 100,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value ? 'Active' : 'Inactive'}
                    color={params.value ? 'success' : 'default'}
                    size="small"
                />
            ),
        },
        {
            field: 'last_triggered_at',
            headerName: 'Last Triggered',
            width: 180,
            valueGetter: (_value: any, row: any) =>
                row.last_triggered_at ? new Date(row.last_triggered_at).toLocaleString() : 'Never',
        },
        {
            field: 'actions',
            headerName: 'Actions',
            width: 320,
            sortable: false,
            filterable: false,
            renderCell: (params: GridRenderCellParams) => {
                const ruleId = params.row.id
                const jp = jobProgress[ruleId]
                const isRunning = jp?.status === 'running'
                return (
                    <Stack direction="row" spacing={0.5} alignItems="center" sx={{ py: 0.5 }}>
                        <Tooltip title={isRunning ? 'Running…' : 'Run now'}>
                            <span>
                                <IconButton
                                    size="small"
                                    color="primary"
                                    disabled={isRunning}
                                    onClick={() => triggerRule(ruleId)}
                                >
                                    <PlayArrowIcon fontSize="small" />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Edit">
                            <IconButton size="small" onClick={() => openEdit(params.row)}>
                                <EditIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete">
                            <IconButton size="small" color="error" onClick={() => deleteRule(ruleId)}>
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        {jp?.status === 'running' && (
                            <Box sx={{ position: 'relative', display: 'inline-flex' }}>
                                <CircularProgress variant="determinate" value={jp.percent} size={34} />
                                <Box sx={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <Typography variant="caption" component="div" sx={{ fontSize: '0.58rem', fontWeight: 600 }}>
                                        {`${jp.percent}%`}
                                    </Typography>
                                </Box>
                            </Box>
                        )}
                        {jp?.status === 'done' && (
                            <Chip size="small" label={`✓ ${jp.processed ?? 0}`} color="success" onDelete={() => dismissProgress(ruleId)} />
                        )}
                        {jp?.status === 'error' && (
                            <Tooltip title={jp.message ?? 'Unknown error'}>
                                <Chip size="small" label="Error" color="error" onDelete={() => dismissProgress(ruleId)} />
                            </Tooltip>
                        )}
                    </Stack>
                )
            },
        },
    ]

    const rows = rules.map(r => ({ ...r, id: r.id }))

    return (
        <Box sx={{ p: 3 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h5">Job Scheduling Rules</Typography>
                <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
                    New Rule
                </Button>
            </Stack>

            {error && (
                <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
                    {error}
                </Alert>
            )}
            {successMsg && (
                <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccessMsg('')}>
                    {successMsg}
                </Alert>
            )}

            {loading && <LinearProgress sx={{ mb: 2 }} />}

            <DataGrid
                rows={rows}
                columns={columns}
                autoHeight
                disableRowSelectionOnClick
                pageSizeOptions={[10, 25, 50]}
                initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
                sx={{ mb: 2 }}
            />

            {/* ── Create / Edit Dialog ──────────────────────────────────── */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>{editingRule ? 'Edit Scheduling Rule' : 'New Scheduling Rule'}</DialogTitle>

                <DialogContent>
                    <Stack spacing={2} mt={1}>
                        <FormControl fullWidth>
                            <InputLabel>Rule Type</InputLabel>
                            <Select
                                label="Rule Type"
                                value={form.rule_type}
                                onChange={(e) => setForm({ ...form, rule_type: e.target.value })}
                            >
                                <MenuItem value="processing">Processing</MenuItem>
                                <MenuItem value="matching">Matching</MenuItem>
                            </Select>
                        </FormControl>

                        <FormControl fullWidth>
                            <InputLabel>Tenants</InputLabel>
                            <Select
                                multiple
                                label="Tenants"
                                value={selectValue}
                                onChange={(e) => handleTenantChange(e.target.value as string[])}
                                input={<OutlinedInput label="Tenants" />}
                                renderValue={(selected) => {
                                    if ((selected as string[]).includes(ALL_TENANTS_SENTINEL)) {
                                        return <Chip size="small" label="All Tenants" />
                                    }
                                    return (
                                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                            {(selected as string[]).map((id) => {
                                                const t = tenants.find((x) => x.id === id)
                                                return <Chip key={id} size="small" label={t?.name ?? id} />
                                            })}
                                        </Box>
                                    )
                                }}
                            >
                                <MenuItem value={ALL_TENANTS_SENTINEL}>
                                    <Checkbox checked={form.tenant_ids.length === 0} />
                                    <ListItemText primary="All Tenants" />
                                </MenuItem>
                                {tenants.map((t) => (
                                    <MenuItem key={t.id} value={t.id}>
                                        <Checkbox checked={form.tenant_ids.includes(t.id)} />
                                        <ListItemText primary={t.name} secondary={t.code} />
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        <FormControl fullWidth>
                            <InputLabel>Frequency</InputLabel>
                            <Select
                                label="Frequency"
                                value={form.frequency}
                                onChange={(e) =>
                                    setForm({ ...form, frequency: e.target.value, day_of_week: 0, day_of_month: 1 })
                                }
                            >
                                <MenuItem value="daily">Once a Day</MenuItem>
                                <MenuItem value="weekly">Once a Week</MenuItem>
                                <MenuItem value="monthly">Once a Month</MenuItem>
                            </Select>
                        </FormControl>

                        {form.frequency === 'weekly' && (
                            <FormControl fullWidth>
                                <InputLabel>Day of Week</InputLabel>
                                <Select
                                    label="Day of Week"
                                    value={form.day_of_week}
                                    onChange={(e) => setForm({ ...form, day_of_week: e.target.value as number })}
                                >
                                    {DAYS_OF_WEEK.map((day, i) => (
                                        <MenuItem key={i} value={i}>{day}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        {form.frequency === 'monthly' && (
                            <FormControl fullWidth>
                                <InputLabel>Day of Month</InputLabel>
                                <Select
                                    label="Day of Month"
                                    value={form.day_of_month}
                                    onChange={(e) => setForm({ ...form, day_of_month: e.target.value as number })}
                                >
                                    {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                                        <MenuItem key={d} value={d}>{d}</MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        <TextField
                            label="Run Time (UTC)"
                            type="time"
                            value={form.run_time}
                            onChange={(e) => setForm({ ...form, run_time: e.target.value })}
                            fullWidth
                            InputLabelProps={{ shrink: true }}
                            inputProps={{ step: 60 }}
                        />

                        <FormControlLabel
                            control={
                                <Switch
                                    checked={form.is_active}
                                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                                />
                            }
                            label="Active"
                        />
                    </Stack>
                </DialogContent>

                <DialogActions>
                    <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
                    <Button variant="contained" onClick={saveRule}>
                        {editingRule ? 'Save Changes' : 'Create Rule'}
                    </Button>
                </DialogActions>
            </Dialog>
        </Box>
    )
}
