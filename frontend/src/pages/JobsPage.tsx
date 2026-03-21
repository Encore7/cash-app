import React, { useEffect, useState } from 'react'
import {
    Alert,
    Box,
    Button,
    Chip,
    Container,
    Dialog,
    DialogActions,
    DialogContent,
    DialogTitle,
    FormControl,
    FormControlLabel,
    IconButton,
    InputLabel,
    LinearProgress,
    MenuItem,
    Paper,
    Select,
    Stack,
    Switch,
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableRow,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import axios from 'axios'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
})

const DAYS_OF_WEEK = [
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
    'Sunday',
]

const EMPTY_FORM = {
    tenant_id: '',
    frequency: 'daily',
    day_of_week: 0,
    day_of_month: 1,
    run_time: '09:00',
    is_active: true,
}

export default function JobsPage() {
    const [rules, setRules] = useState([])
    const [tenants, setTenants] = useState([])
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [successMsg, setSuccessMsg] = useState('')
    const [dialogOpen, setDialogOpen] = useState(false)
    const [editingRule, setEditingRule] = useState(null)
    const [form, setForm] = useState(EMPTY_FORM)

    useEffect(() => {
        fetchRules()
        fetchTenants()
    }, [])

    async function fetchRules() {
        setLoading(true)
        try {
            const { data } = await api.get('/jobs/rules')
            setRules(data)
        } catch (e) {
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
            // tenants list is optional — ignore failures silently
        }
    }

    function openCreate() {
        setEditingRule(null)
        setForm(EMPTY_FORM)
        setDialogOpen(true)
    }

    function openEdit(rule) {
        setEditingRule(rule)
        setForm({
            tenant_id: rule.tenant_id || '',
            frequency: rule.frequency,
            day_of_week: rule.day_of_week ?? 0,
            day_of_month: rule.day_of_month ?? 1,
            run_time: rule.run_time,
            is_active: rule.is_active,
        })
        setDialogOpen(true)
    }

    async function saveRule() {
        const payload = {
            tenant_id: form.tenant_id || null,
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
                setSuccessMsg('Rule created successfully')
            }
            setDialogOpen(false)
            fetchRules()
        } catch (e) {
            setError(e?.response?.data?.detail || e.message)
        }
    }

    async function deleteRule(id) {
        try {
            await api.delete(`/jobs/rules/${id}`)
            setSuccessMsg('Rule deleted')
            fetchRules()
        } catch (e) {
            setError(e?.response?.data?.detail || e.message)
        }
    }

    async function triggerRule(id) {
        setSuccessMsg('')
        setError('')
        try {
            const { data } = await api.post(`/jobs/rules/${id}/trigger`)
            setSuccessMsg(
                `Job triggered: ${data.processed} tenant/date pair(s) processed`,
            )
            fetchRules()
        } catch (e) {
            setError(e?.response?.data?.detail || e.message)
        }
    }

    function frequencyLabel(freq) {
        if (freq === 'daily') return 'Daily'
        if (freq === 'weekly') return 'Weekly'
        if (freq === 'monthly') return 'Monthly'
        return freq
    }

    function scheduleDetail(rule) {
        if (rule.frequency === 'weekly' && rule.day_of_week != null)
            return DAYS_OF_WEEK[rule.day_of_week]
        if (rule.frequency === 'monthly' && rule.day_of_month != null)
            return `Day ${rule.day_of_month}`
        return '—'
    }

    return (
        <Container sx={{ py: 3 }}>
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

            <Paper>
                <Table>
                    <TableHead>
                        <TableRow>
                            <TableCell>Tenant</TableCell>
                            <TableCell>Frequency</TableCell>
                            <TableCell>Day / Date</TableCell>
                            <TableCell>Time (UTC)</TableCell>
                            <TableCell>Status</TableCell>
                            <TableCell>Last Triggered</TableCell>
                            <TableCell align="right">Actions</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {rules.map((rule) => (
                            <TableRow key={rule.id} hover>
                                <TableCell>
                                    {rule.tenant_code ? `${rule.tenant_name} (${rule.tenant_code})` : 'All Tenants'}
                                </TableCell>
                                <TableCell>
                                    <Chip
                                        label={frequencyLabel(rule.frequency)}
                                        size="small"
                                        color={
                                            rule.frequency === 'daily'
                                                ? 'primary'
                                                : rule.frequency === 'weekly'
                                                    ? 'secondary'
                                                    : 'default'
                                        }
                                    />
                                </TableCell>
                                <TableCell>{scheduleDetail(rule)}</TableCell>
                                <TableCell>{rule.run_time}</TableCell>
                                <TableCell>
                                    <Chip
                                        label={rule.is_active ? 'Active' : 'Inactive'}
                                        color={rule.is_active ? 'success' : 'default'}
                                        size="small"
                                    />
                                </TableCell>
                                <TableCell>
                                    {rule.last_triggered_at
                                        ? new Date(rule.last_triggered_at).toLocaleString()
                                        : 'Never'}
                                </TableCell>
                                <TableCell align="right">
                                    <Tooltip title="Trigger now">
                                        <IconButton onClick={() => triggerRule(rule.id)} color="primary" size="small">
                                            <PlayArrowIcon />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Edit">
                                        <IconButton onClick={() => openEdit(rule)} size="small">
                                            <EditIcon />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Delete">
                                        <IconButton onClick={() => deleteRule(rule.id)} color="error" size="small">
                                            <DeleteIcon />
                                        </IconButton>
                                    </Tooltip>
                                </TableCell>
                            </TableRow>
                        ))}

                        {!loading && rules.length === 0 && (
                            <TableRow>
                                <TableCell colSpan={7} align="center" sx={{ py: 4 }}>
                                    <Typography color="text.secondary">
                                        No scheduling rules configured. Click "New Rule" to add one.
                                    </Typography>
                                </TableCell>
                            </TableRow>
                        )}
                    </TableBody>
                </Table>
            </Paper>

            {/* Create / Edit Dialog */}
            <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
                <DialogTitle>{editingRule ? 'Edit Scheduling Rule' : 'New Scheduling Rule'}</DialogTitle>

                <DialogContent>
                    <Stack spacing={2} mt={1}>
                        {/* Tenant */}
                        <FormControl fullWidth>
                            <InputLabel>Tenant</InputLabel>
                            <Select
                                label="Tenant"
                                value={form.tenant_id}
                                onChange={(e) => setForm({ ...form, tenant_id: e.target.value })}
                            >
                                <MenuItem value="">All Tenants</MenuItem>
                                {tenants.map((t) => (
                                    <MenuItem key={t.id} value={t.id}>
                                        {t.name} ({t.code})
                                    </MenuItem>
                                ))}
                            </Select>
                        </FormControl>

                        {/* Frequency */}
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

                        {/* Day of week (weekly only) */}
                        {form.frequency === 'weekly' && (
                            <FormControl fullWidth>
                                <InputLabel>Day of Week</InputLabel>
                                <Select
                                    label="Day of Week"
                                    value={form.day_of_week}
                                    onChange={(e) => setForm({ ...form, day_of_week: e.target.value })}
                                >
                                    {DAYS_OF_WEEK.map((day, i) => (
                                        <MenuItem key={i} value={i}>
                                            {day}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        {/* Day of month (monthly only) */}
                        {form.frequency === 'monthly' && (
                            <FormControl fullWidth>
                                <InputLabel>Day of Month</InputLabel>
                                <Select
                                    label="Day of Month"
                                    value={form.day_of_month}
                                    onChange={(e) => setForm({ ...form, day_of_month: e.target.value })}
                                >
                                    {Array.from({ length: 28 }, (_, i) => i + 1).map((d) => (
                                        <MenuItem key={d} value={d}>
                                            {d}
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl>
                        )}

                        {/* Time */}
                        <TextField
                            label="Run Time (UTC)"
                            type="time"
                            value={form.run_time}
                            onChange={(e) => setForm({ ...form, run_time: e.target.value })}
                            fullWidth
                            InputLabelProps={{ shrink: true }}
                            inputProps={{ step: 60 }}
                        />

                        {/* Active toggle */}
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
        </Container>
    )
}
