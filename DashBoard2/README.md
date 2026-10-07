# NodeX — Dashboard 2 (View-Only Cloud Telemetry Web App)

Dashboard 2 is a lightweight, strictly **READ-ONLY** web client for the NodeX proximity security ecosystem. It communicates directly and exclusively with Supabase to display registered laptops, ESP32 BLE tokens, security events, webcam intruder captures, alerts, and analytics.

It never contacts the local daemon (`127.0.0.1:7878`) and functions completely independently even when the laptop and ESP32 hardware are turned off.

---

## 🔒 Hard Security Guarantees
- **Strictly Read-Only**: Performs zero mutations (`insert`, `update`, `upsert`, `delete`, or storage write/remove). Only `select` queries and `createSignedUrl` are executed.
- **Client Security**: Uses strictly the public **Anon key** (`VITE_SUPABASE_ANON_KEY`) with an authenticated user session. The `service_role` key is never used or embedded.
- **Signed Storage Access**: Webcam photos in the private `intruder-captures` bucket are generated on-demand with a 5-minute time-to-live (TTL).

---

## 🛠️ Tech Stack
- **Framework**: React 18 + Vite (JavaScript)
- **Styling**: Tailwind CSS (`darkMode: "class"`), custom glassmorphism, matching Dashboard 1 design tokens
- **Typography**: `@fontsource/inter` and `@fontsource/jetbrains-mono` bundled locally (no Google Fonts CDN)
- **Motion**: Framer Motion (opacity and transform animations only, respects `prefers-reduced-motion`)
- **Icons**: Lucide React
- **Routing & Client**: `react-router-dom`, `@supabase/supabase-js`
- **Visuals**: Hand-built responsive SVG/CSS bar charts (no external charting libraries)

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
cd DashBoard2
npm install
```

### 2. Configure Environment Variables
Copy the template file to `.env`:
```bash
cp .env.example .env
```
Ensure your `.env` contains:
```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-public-key
```

### 3. Run Development Server
```bash
npm run dev
```
Open `http://localhost:5173` in your browser.

### 4. Build for Production
```bash
npm run build
```
The optimized static bundle will be generated in `dist/`.

---

## 🌐 Deployment

Because Dashboard 2 produces a pure static bundle in `dist/`, it can be hosted anywhere:

### Netlify
```bash
npx netlify deploy --prod --dir=dist
```
Or link your Git repository with:
- Build command: `npm run build`
- Publish directory: `dist`
- Add environment variables `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` in Netlify Site Settings.

### Vercel
```bash
npx vercel --prod
```
Or import the repository into Vercel:
- Framework preset: `Vite`
- Root directory: `DashBoard2`
- Build command: `npm run build`
- Output directory: `dist`
- Add your environment variables in the Vercel project settings.

### GitHub Pages
1. In `vite.config.js`, set `base: '/repository-name/'` if hosting on a subpath.
2. Build with `npm run build`.
3. Deploy the contents of `dist/` to the `gh-pages` branch.

---

## 🔐 Supabase Read-Only Policies

If you need to guarantee that your Supabase Auth user has SELECT access, open the Supabase SQL Editor and execute:
```sql
-- See DashBoard2/supabase/dashboard2_read.sql
```
This script creates idempotent, strictly `SELECT`-only policies on all tables and the `intruder-captures` storage bucket.
