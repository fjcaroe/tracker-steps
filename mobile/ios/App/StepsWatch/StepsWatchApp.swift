import SwiftUI
import WatchConnectivity

struct WatchModule: Codable, Identifiable {
    let id: String
    let name: String
}
struct WatchSnapshot: Codable {
    let version: Int
    let issuedAt: Double
    let validUntil: Double
    let scope: String
    let state: String
    let company: String
    let demo: Bool
    let modules: [WatchModule]
    let pending: Int
    let problems: Int
    let syncing: Bool
    var fresh: Bool { version == 1 && state == "ready" && validUntil > Date().timeIntervalSince1970 * 1000 && issuedAt <= Date().timeIntervalSince1970 * 1000 + 30_000 }
}

final class WatchStore: NSObject, ObservableObject, WCSessionDelegate {
    @Published private(set) var snapshot: WatchSnapshot?
    @Published var message = ""

    override init() {
        super.init()
        // No disk cache: after restarting, wait for the current phone's context.
        if WCSession.isSupported() {
            WCSession.default.delegate = self
            WCSession.default.activate()
        }
    }
    private func receive(_ value: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: value),
              let next = try? JSONDecoder().decode(WatchSnapshot.self, from: data), next.version == 1 else { return }
        DispatchQueue.main.async {
            if let old = self.snapshot, next.issuedAt < old.issuedAt { return }
            self.snapshot = next
        }
    }
    func refresh() {
        guard WCSession.default.activationState == .activated, WCSession.default.isReachable else {
            message = "Abre Steps en tu iPhone para actualizar."; return
        }
        WCSession.default.sendMessage(["request": "refresh"], replyHandler: { reply in
            if let value = reply["snapshot"] as? [String: Any] { self.receive(value) }
        }, errorHandler: { _ in DispatchQueue.main.async { self.message = "No se pudo conectar. Abre Steps en el iPhone." } })
    }
    func open(_ module: WatchModule) {
        guard let current = snapshot, current.fresh, WCSession.default.isReachable else {
            message = "Abre Steps en tu iPhone y actualiza el resumen."; return
        }
        WCSession.default.sendMessage(["request": "openModule", "module": module.id, "scope": current.scope], replyHandler: { reply in
            DispatchQueue.main.async { self.message = (reply["accepted"] as? Bool == true) ? "Solicitud enviada. Revisa Steps en tu iPhone." : "Tu acceso cambió. Actualiza desde el iPhone." }
        }, errorHandler: { _ in DispatchQueue.main.async { self.message = "No se envió la solicitud. Usa el iPhone." } })
    }
    func session(_ session: WCSession, activationDidCompleteWith activationState: WCSessionActivationState, error: Error?) {
        receive(session.receivedApplicationContext)
        DispatchQueue.main.async { self.refresh() }
    }
    func session(_ session: WCSession, didReceiveApplicationContext applicationContext: [String: Any]) { receive(applicationContext) }
    func session(_ session: WCSession, didReceiveMessage message: [String: Any]) {
        if let value = message["snapshot"] as? [String: Any] { receive(value) }
    }
}

@main
struct StepsWatchApp: App {
    @StateObject private var store = WatchStore()
    @Environment(\.scenePhase) private var phase
    var body: some Scene {
        WindowGroup {
            TimelineView(.periodic(from: .now, by: 15)) { _ in
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("Steps").font(.title2.bold()).foregroundStyle(.green)
                        if let s = store.snapshot, s.fresh {
                            if s.demo { Text("DEMOSTRACIÓN").font(.caption.bold()).foregroundStyle(.orange) }
                            Text(s.company).font(.headline)
                            Label(s.syncing ? "Enviando…" : "\(s.pending) por enviar", systemImage: "arrow.triangle.2.circlepath")
                            Text("Colaciones y Movilización").font(.caption2).foregroundStyle(.secondary)
                            if s.problems > 0 { Label("\(s.problems) requieren revisión", systemImage: "exclamationmark.triangle").foregroundStyle(.orange) }
                            ForEach(s.modules) { module in
                                Button { store.open(module) } label: { VStack(alignment: .leading) { Text(module.name); Text("Abrir en iPhone").font(.caption2) } }
                            }
                            if s.modules.isEmpty { Text("No tienes módulos habilitados.") }
                            Text("Actualizado \(Date(timeIntervalSince1970: s.issuedAt / 1000), style: .time)").font(.caption2).foregroundStyle(.secondary)
                        } else {
                            Text("Abre Steps en tu iPhone y habilita el resumen en Perfil → Apple Watch.")
                            Text("El resumen caduca a los cinco minutos sin actualizar.").font(.caption2).foregroundStyle(.secondary)
                        }
                        Button("Actualizar") { store.refresh() }
                        if !store.message.isEmpty { Text(store.message).font(.caption) }
                    }.padding(.horizontal, 4)
                }
            }.onChange(of: phase) { phase in if phase == .active { store.refresh() } }
        }
    }
}
