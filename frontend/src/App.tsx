import { Route, Routes } from 'react-router-dom'

export default function App() {
  return (
    <Routes>
      <Route path="*" element={<p className="p-8">MeterMachen 🚧</p>} />
    </Routes>
  )
}
