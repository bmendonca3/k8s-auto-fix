import types
import unittest

import yaml

from src.verifier.verifier import Verifier
from src.proposer import cli as proposer_cli

PRIVILEGED_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: privileged
spec:
  containers:
    - name: ubuntu
      image: ubuntu:22.04
      securityContext:
        privileged: true
"""

LATEST_MANIFEST = """
apiVersion: v1
kind: Pod
metadata:
  name: latest
spec:
  containers:
    - name: nginx
      image: nginx:latest
"""

CRONJOB_MANIFEST = """
apiVersion: batch/v1beta1
kind: CronJob
metadata:
  name: demo
spec:
  jobTemplate:
    template:
      spec:
        containers:
          - name: scanner
            image: artifacthub/scanner:latest
"""


class VerifierTests(unittest.TestCase):
    def _stub_kubectl(self, verifier: Verifier, value: bool, message: str | None = None) -> None:
        verifier._kubectl_dry_run = types.MethodType(
            lambda _self, _yaml: (value, message, 0), verifier
        )

    def test_verify_successful_patch(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        patch = [{"op": "replace", "path": "/spec/containers/0/image", "value": "nginx:stable"}]
        result = verifier.verify(LATEST_MANIFEST, patch, "no_latest_tag")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_schema)
        self.assertTrue(result.ok_policy)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)
        self.assertIsNotNone(result.patched_yaml)

    def test_verify_policy_failure(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        # Patch changes unrelated field, leaving privileged true
        patch = [{"op": "add", "path": "/metadata/labels/env", "value": "prod"}]
        result = verifier.verify(PRIVILEGED_MANIFEST, patch, "no_privileged")
        self.assertFalse(result.accepted)
        self.assertFalse(result.ok_policy)
        self.assertFalse(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_schema_failure(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, False, "spec.containers[0].image: Invalid value")
        patch = [{"op": "replace", "path": "/spec/containers/0/image", "value": "ubuntu:stable"}]
        result = verifier.verify(PRIVILEGED_MANIFEST, patch, "no_privileged")
        self.assertFalse(result.ok_schema)
        self.assertFalse(result.accepted)
        self.assertFalse(result.ok_safety)
        self.assertTrue(result.ok_rescan)
        self.assertTrue(
            any("kubectl dry-run failed" in err for err in result.errors),
            msg=f"kubectl failure detail missing in {result.errors}",
        )

    def test_collect_containers_handles_cronjob_template(self) -> None:
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        obj = yaml.safe_load(CRONJOB_MANIFEST)
        patch = proposer_cli._patch_no_latest(obj)
        result = verifier.verify(CRONJOB_MANIFEST, patch, "no_latest_tag")
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.accepted)

    def test_verify_invalid_patch(self) -> None:
        verifier = Verifier()
        self._stub_kubectl(verifier, True)
        patch = [{"op": "replace", "path": "/spec/containers/1/image", "value": "nginx:stable"}]
        result = verifier.verify(LATEST_MANIFEST, patch, "no_latest_tag")
        self.assertFalse(result.accepted)
        self.assertFalse(result.ok_safety)
        self.assertTrue(result.ok_rescan)
        self.assertIsNone(result.patched_yaml)

    def test_verify_host_path_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: hostpath-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      hostPath:
        path: /var/lib/data
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_host_path(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_host_path")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_host_ports_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: hostport-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      ports:
        - containerPort: 80
          hostPort: 30080
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_host_ports(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_host_ports")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_run_as_user_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: runasuser-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_run_as_user(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "run_as_user")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_run_as_non_root_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: runasnonroot-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_run_as_non_root(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "run_as_non_root")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_read_only_root_fs_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: readonlyfs-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_read_only_root_fs(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "read_only_root_fs")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_set_requests_limits_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: requests-limits
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_set_requests_limits(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "set_requests_limits")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_enforce_seccomp_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: seccomp-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_enforce_seccomp(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "enforce_seccomp")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_drop_capabilities_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: caps-pod
spec:
  containers:
    - name: app
      image: nginx:1.23
      securityContext:
        capabilities:
          add: ["NET_RAW", "CHOWN"]
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_drop_capabilities(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "drop_capabilities")
        self.assertTrue(result.accepted)

    def test_patch_drop_capabilities_multiple_containers(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: caps-many
spec:
  containers:
    - name: first
      image: nginx:1.23
      securityContext:
        privileged: true
        capabilities:
          add:
            - NET_RAW
    - name: second
      image: busybox:stable
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_drop_capabilities(obj)
        paths = {op["path"] for op in patch}
        self.assertIn("/spec/containers/0/securityContext/privileged", paths)
        self.assertTrue(any("/spec/containers/1/securityContext" in path for path in paths))
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "drop_capabilities")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_verify_dangling_service_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Service
metadata:
  name: orphan-service
  namespace: demo
  labels:
    app: orphan
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8080
"""
        obj = yaml.safe_load(manifest)
        selector_hint = proposer_cli._assert_service_safety(obj)
        patch = proposer_cli._patch_dangling_service(obj, selector_hint=selector_hint)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "dangling_service")
        self.assertTrue(result.accepted)
        self.assertTrue(result.ok_safety)
        self.assertTrue(result.ok_rescan)

    def test_dangling_service_requires_manual_review_when_selector_exists(self) -> None:
        manifest = """
apiVersion: v1
kind: Service
metadata:
  name: existing-selector
spec:
  type: ClusterIP
  selector:
    app: existing
  ports:
    - port: 443
      targetPort: 8443
"""
        obj = yaml.safe_load(manifest)
        with self.assertRaises(proposer_cli.PatchError):
            proposer_cli._assert_service_safety(obj)

    def test_dangling_service_rejects_nodeport(self) -> None:
        manifest = """
apiVersion: v1
kind: Service
metadata:
  name: nodeport-svc
spec:
  type: NodePort
  ports:
    - port: 80
      targetPort: 8080
"""
        obj = yaml.safe_load(manifest)
        with self.assertRaises(proposer_cli.PatchError):
            proposer_cli._assert_service_safety(obj)

    def test_placeholder_sanitisation_expands_identifiers(self) -> None:
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: "__RESOURCE__"
  namespace: "__NAMESPACE__"
  labels:
    app: "__APP__"
spec:
  selector:
    matchLabels:
      app: "__APP__"
    matchExpressions:
      - key: tier
        operator: In
        values:
          - "__TIER__"
  template:
    metadata:
      labels:
        app: "__APP__"
    spec:
      imagePullSecrets:
        - name: "__PULL_SECRET__"
      volumes:
        - name: conf
          secret:
            secretName: "__SECRET_NAME__"
      containers:
        - name: api
          image: nginx
          env:
            - name: APP_SECRET
              value: foo
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: "__EXISTING_SECRET__"
                  key: "__DB__"
          envFrom:
            - secretRef:
                name: "__SECRET_REF__"
"""
        obj = yaml.safe_load(manifest)
        ops = proposer_cli._patch_namespace_placeholders(obj)
        patch_map = {entry["path"]: entry["value"] for entry in ops if entry["op"] == "replace"}
        self.assertEqual(patch_map["/metadata/name"], "resource")
        self.assertEqual(patch_map["/metadata/namespace"], "namespace")
        self.assertEqual(patch_map["/metadata/labels/app"], "placeholder")
        self.assertEqual(patch_map["/spec/selector/matchLabels/app"], "placeholder")
        self.assertEqual(patch_map["/spec/selector/matchExpressions/0/values/0"], "placeholder")
        self.assertEqual(patch_map["/spec/template/metadata/labels/app"], "placeholder")
        self.assertEqual(patch_map["/spec/template/spec/imagePullSecrets/0/name"], "pull-secret")
        self.assertEqual(patch_map["/spec/template/spec/volumes/0/secret/secretName"], "secret-name")
        self.assertEqual(
            patch_map["/spec/template/spec/containers/0/env/1/valueFrom/secretKeyRef/name"],
            "existing-secret",
        )
        self.assertEqual(
            patch_map["/spec/template/spec/containers/0/env/1/valueFrom/secretKeyRef/key"],
            "db",
        )
        self.assertEqual(
            patch_map["/spec/template/spec/containers/0/envFrom/0/secretRef/name"],
            "secret-ref",
        )

    def test_missing_metadata_name_guard_infers_from_labels(self) -> None:
        manifest = """
apiVersion: batch/v1
kind: Job
metadata:
  labels:
    app: gitops-runner
spec:
  template:
    spec:
      containers:
        - name: runner
          image: busybox
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_missing_metadata_name(obj)
        self.assertEqual(patch[0]["path"], "/metadata/name")
        self.assertEqual(patch[0]["value"], "gitops-runner")

    def test_verify_env_var_secret_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: secret-env
spec:
  containers:
    - name: app
      image: nginx:1.23
      env:
        - name: APP_SECRET
          value: supersecret
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_env_var_secret(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "env_var_secret")
        self.assertTrue(result.accepted)

    def test_env_var_secret_converts_multiple_variables(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: multi-secret
spec:
  containers:
    - name: app
      image: nginx:1.23
      env:
        - name: APP_SECRET
          value: supersecret
        - name: DB_PASSWORD
          value: admin
        - name: TOKEN
          valueFrom:
            configMapKeyRef:
              name: config-source
              key: token
  volumes:
    - name: shared
      secret:
        secretName: existing-secret
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_env_var_secret(obj)
        self.assertEqual(len(patch), 2)
        first_ref = patch[0]["value"]["valueFrom"]["secretKeyRef"]
        second_ref = patch[1]["value"]["valueFrom"]["secretKeyRef"]
        self.assertEqual(first_ref["name"], "existing-secret")
        self.assertEqual(second_ref["name"], "existing-secret")
        self.assertEqual({first_ref["key"], second_ref["key"]}, {"app_secret", "db_password"})

    def test_env_var_secret_converts_configmap_reference(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: config-secret
spec:
  containers:
    - name: app
      image: nginx:1.23
      env:
        - name: API_PASSWORD
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: api-password
  volumes:
    - name: shared
      secret:
        secretName: shared-secret
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_env_var_secret(obj)
        self.assertEqual(len(patch), 1)
        secret_ref = patch[0]["value"]["valueFrom"]["secretKeyRef"]
        self.assertEqual(secret_ref["name"], "shared-secret")
        self.assertEqual(secret_ref["key"], "api_password")

    def test_env_var_secret_reuses_existing_secret(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: secret-env
spec:
  containers:
    - name: app
      image: nginx:1.23
      env:
        - name: DB_PASSWORD
          value: supersecret
      volumeMounts:
        - name: db-secret
          mountPath: /var/run/db
  volumes:
    - name: db-secret
      secret:
        secretName: prod-db-credentials
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_env_var_secret(obj)
        secret_ref = patch[0]["value"]["valueFrom"]["secretKeyRef"]
        self.assertEqual(secret_ref["name"], "prod-db-credentials")
        self.assertEqual(secret_ref["key"], "db_password")
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "env_var_secret")
        self.assertTrue(result.accepted)

    def test_env_var_secret_matches_item_paths(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: jenkins-like
spec:
  containers:
    - name: app
      image: nginx:1.23
      env:
        - name: ADMIN_PASSWORD
          value: /run/secrets/additional/chart-admin-password
      volumeMounts:
        - name: jenkins-secrets
          mountPath: /run/secrets/additional
  volumes:
    - name: jenkins-secrets
      secret:
        secretName: release-name-jenkins
        items:
          - key: jenkins-admin-user
            path: chart-admin-username
          - key: jenkins-admin-password
            path: chart-admin-password
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_env_var_secret(obj)
        secret_ref = patch[0]["value"]["valueFrom"]["secretKeyRef"]
        self.assertEqual(secret_ref["name"], "release-name-jenkins")
        self.assertEqual(secret_ref["key"], "jenkins-admin-password")
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "env_var_secret")
        self.assertTrue(result.accepted)

    def test_missing_volumes_guard_seeds_emptydir(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: volume-missing
spec:
  containers:
    - name: app
      image: nginx
      volumeMounts:
        - name: data
          mountPath: /data
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_missing_volumes(obj)
        self.assertEqual(patch[0]["path"], "/spec/volumes")
        self.assertEqual(patch[0]["value"], [{"name": "data", "emptyDir": {}}])

    def test_requests_within_limits_guard_clamps_values(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: resource-adjust
spec:
  containers:
    - name: app
      image: nginx
      resources:
        limits:
          cpu: "100m"
          memory: 256Mi
        requests:
          cpu: "200m"
          memory: 1Gi
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_requests_within_limits(obj)
        paths = {entry["path"]: entry["value"] for entry in patch}
        self.assertEqual(paths["/spec/containers/0/resources/requests/cpu"], "100m")
        self.assertEqual(paths["/spec/containers/0/resources/requests/memory"], "256Mi")

    def test_verify_liveness_port_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: liveness-port
spec:
  containers:
    - name: app
      image: nginx:1.23
      livenessProbe:
        httpGet:
          path: /healthz
          port: 8080
          scheme: HTTP
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_probe_port(obj, "liveness")  # type: ignore[attr-defined]
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "liveness_port")
        self.assertTrue(result.accepted)

    def test_verify_liveness_port_named_port(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: liveness-named
spec:
  containers:
    - name: app
      image: nginx:1.23
      livenessProbe:
        httpGet:
          path: /metrics
          port: monitoring
      ports:
        - name: monitoring
          containerPort: 9090
"""
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, [], "liveness_port")
        self.assertTrue(result.accepted)

    def test_verify_readiness_port_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: readiness-port
spec:
  containers:
    - name: app
      image: nginx:1.23
      readinessProbe:
        httpGet:
          path: /ready
          port: 9090
          scheme: HTTP
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_probe_port(obj, "readiness")  # type: ignore[attr-defined]
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "readiness_port")
        self.assertTrue(result.accepted)

    def test_verify_startup_port_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: startup-port
spec:
  containers:
    - name: app
      image: nginx:1.23
      startupProbe:
        httpGet:
          path: /started
          port: 7070
          scheme: HTTP
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_probe_port(obj, "startup")  # type: ignore[attr-defined]
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "startup_port")
        self.assertTrue(result.accepted)

    def test_verify_liveness_port_tcp_socket(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: tcp-liveness-port
spec:
  containers:
    - name: app
      image: redis:7
      livenessProbe:
        tcpSocket:
          port: 6379
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_probe_port(obj, "liveness")  # type: ignore[attr-defined]
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "liveness_port")
        self.assertTrue(result.accepted)

    def test_verify_no_latest_tag_adds_missing_image(self) -> None:
        manifest = """
apiVersion: batch/v1
kind: Job
metadata:
  name: worker
spec:
  template:
    spec:
      containers:
        - name: runner
          command:
            - echo
            - hello
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_latest(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_latest_tag")
        self.assertTrue(result.accepted)

    def test_patch_no_latest_updates_all_containers(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: multi
spec:
  containers:
    - name: first
      image: nginx:latest
    - name: second
      image: busybox
  initContainers:
    - name: init
      command: ["echo", "hi"]
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_latest(obj)
        paths = [op["path"] for op in patch]
        self.assertIn("/spec/containers/0/image", paths)
        self.assertIn("/spec/containers/1/image", paths)
        self.assertIn("/spec/initContainers/0/image", paths)


    def test_verify_non_existent_service_account_policy(self) -> None:
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
spec:
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
      annotations:
        k8s-auto-fix.dev/allow-default-service-account: "true"
    spec:
      serviceAccountName: missing-account
      containers:
        - name: app
          image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        proposer_cli._assert_service_account_safety(obj)
        patch = proposer_cli._patch_non_existent_service_account(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "non_existent_service_account")
        self.assertTrue(result.accepted)

    def test_service_account_patch_requires_opt_in(self) -> None:
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo
spec:
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      serviceAccountName: missing-account
      containers:
        - name: app
          image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        with self.assertRaises(proposer_cli.PatchError):
            proposer_cli._assert_service_account_safety(obj)

    def test_verify_cronjob_policy(self) -> None:
        manifest = """
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly
spec:
  schedule: "0 0 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: app
              image: nginx:latest
          restartPolicy: OnFailure
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_latest(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_latest_tag")
        self.assertTrue(result.accepted)

    def test_cronjob_defaults_guard(self) -> None:
        manifest = """
apiVersion: batch/v1
kind: CronJob
metadata:
  name: nightly
spec:
  jobTemplate:
    template:
      spec:
        containers:
          - name: app
            image: nginx:latest
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_cronjob_defaults(obj)
        paths = {op["path"] for op in patch}
        self.assertIn("/spec/schedule", paths)
        self.assertIn("/spec/jobTemplate/spec/template/spec/restartPolicy", paths)
        self.assertIn("/spec/jobTemplate/template", paths)

    def test_verify_pdb_policy(self) -> None:
        manifest = """
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: example
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: web
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_pdb_unhealthy_eviction(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "pdb_unhealthy_eviction_policy")
        self.assertTrue(result.accepted)

    def test_verify_job_ttl_policy(self) -> None:
        manifest = """
apiVersion: batch/v1
kind: Job
metadata:
  name: cleanup
spec:
  template:
    spec:
      containers:
        - name: job
          image: busybox
      restartPolicy: Never
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_job_ttl_after_finished(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "job_ttl_after_finished")
        self.assertTrue(result.accepted)

    def test_verify_unsafe_sysctls_policy(self) -> None:
        manifest = """
apiVersion: v1
kind: Pod
metadata:
  name: sysctl-test
spec:
  securityContext:
    sysctls:
      - name: net.ipv4.ip_forward
        value: "1"
  containers:
    - name: app
      image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_unsafe_sysctls(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "unsafe_sysctls")
        self.assertTrue(result.accepted)

    def test_verify_deprecated_service_account_policy(self) -> None:
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: legacy-sa
spec:
  selector:
    matchLabels:
      app: legacy
  template:
    metadata:
      labels:
        app: legacy
    spec:
      serviceAccount: legacy-sa
      containers:
        - name: app
          image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_deprecated_service_account_field(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "deprecated_service_account_field")
        self.assertTrue(result.accepted)

    def test_verify_no_anti_affinity_policy(self) -> None:
        manifest = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: app
  template:
    metadata:
      labels:
        app: app
    spec:
      containers:
        - name: app
          image: nginx:1.23
"""
        obj = yaml.safe_load(manifest)
        patch = proposer_cli._patch_no_anti_affinity(obj)
        verifier = Verifier(require_kubectl=False)
        self._stub_kubectl(verifier, True)
        result = verifier.verify(manifest, patch, "no_anti_affinity")
        self.assertTrue(result.accepted)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
