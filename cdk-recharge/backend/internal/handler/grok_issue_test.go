package handler

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/gin-gonic/gin"
	"github.com/tuzi/cdk-recharge-system/internal/db"
)

// Grok 发码：拉 Grok 档位表、对卡台显式发 grok_ 前缀档位、地区固定 US。
func TestGrokIssueUsesGrokCatalogueAndPrefixedPlan(t *testing.T) {
	c, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	c.SetMaxOpenConns(1)
	old := db.DB
	db.DB = c
	t.Cleanup(func() { db.DB = old; c.Close() })
	for _, q := range []string{`CREATE TABLE site_settings(key TEXT PRIMARY KEY,value TEXT,updated_at DATETIME)`, `CREATE TABLE cardplatform_cdk_codes(upstream_id INTEGER,code TEXT UNIQUE NOT NULL,code_prefix TEXT,plan TEXT,fee_amount_minor INTEGER,status TEXT,payment_country TEXT,created_at DATETIME)`} {
		if _, err = c.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	issued := 0
	catalogueStatus := http.StatusOK
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/openapi/v1/gpt-direct/plans":
			if catalogueStatus != http.StatusOK {
				w.WriteHeader(catalogueStatus)
				return
			}
			if r.URL.Query().Get("product") != "grok" {
				t.Error("Grok issue fetched another catalogue")
			}
			w.Write([]byte(`{"code":0,"data":{"version":1,"plans":{"grok_monthly":{"enabled":true,"currency":"USD"}},"registry":[{"key":"monthly","label":"SuperGrok"}]}}`))
		case "/openapi/v1/gpt-direct/cdks":
			var b map[string]any
			if err := json.NewDecoder(r.Body).Decode(&b); err != nil {
				t.Error(err)
			}
			if b["plan"] != "grok_monthly" || b["payment_country"] != "US" {
				t.Errorf("wrong Grok issue parameters %v", b)
			}
			issued++
			w.Write([]byte(`{"code":0,"data":{"requested":1,"issued":[{"id":1,"code":"ZC-FAKE-TEST-GROK-CODE","plan":"monthly","payment_country":"US"}]}}`))
		default:
			t.Errorf("unexpected endpoint %s", r.URL.Path)
			w.WriteHeader(404)
		}
	}))
	defer s.Close()
	if e := db.SetSetting("card_api_base", s.URL); e != nil {
		t.Fatal(e)
	}
	if e := db.SetSetting("card_api_key", "fixture-key"); e != nil {
		t.Fatal(e)
	}
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.POST("/issue", CardPlatformIssueCDKs)
	for _, body := range []string{
		`{"plan":"monthly","product":"grok","count":1,"funding_confirmed":true,"payment_country":"PH"}`,
		`{"plan":"grok_monthly","count":1,"funding_confirmed":true}`, // 老前端不传 product：按档位推断
	} {
		req := httptest.NewRequest("POST", "/issue", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != 200 {
			t.Fatalf("Grok issue failed %d %s", w.Code, w.Body.String())
		}
	}
	if issued != 2 {
		t.Fatalf("issued %d", issued)
	}
	for _, tc := range []struct {
		body   string
		status int
	}{
		{`{"plan":"heavy_yearly","product":"grok","count":1,"funding_confirmed":true}`, 200},
		{`{"plan":"monthly","product":"grok","count":1,"funding_confirmed":true}`, 503},
		{`{"plan":"monthly","product":"gpt","count":1,"funding_confirmed":true}`, 503},
		{`{"plan":"basic_monthly","product":"gpt","count":1,"funding_confirmed":true}`, 503},
	} {
		catalogueStatus = tc.status
		req := httptest.NewRequest("POST", "/issue", strings.NewReader(tc.body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest || issued != 2 {
			t.Fatalf("unavailable or mismatched product reached issuance: status=%d issued=%d", w.Code, issued)
		}
	}
	r.GET("/plans", PublicCDKPlans)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest("GET", "/plans?product=grok", nil))
	if w.Code != http.StatusServiceUnavailable || strings.Contains(w.Body.String(), "docs_default") {
		t.Fatalf("Grok must not fall back to GPT catalogue: %d %s", w.Code, w.Body.String())
	}
}

func TestGrokPreflightDoesNotBindBillingSession(t *testing.T) {
	c, err := sql.Open("sqlite3", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	c.SetMaxOpenConns(1)
	old := db.DB
	db.DB = c
	t.Cleanup(func() { db.DB = old; c.Close() })
	for _, q := range []string{
		`CREATE TABLE site_settings(key TEXT PRIMARY KEY,value TEXT,updated_at DATETIME)`,
		`CREATE TABLE cdk_session_bindings(cdk_code TEXT PRIMARY KEY,session_payload TEXT NOT NULL,redemption_token TEXT,updated_at DATETIME)`,
	} {
		if _, err := c.Exec(q); err != nil {
			t.Fatal(err)
		}
	}
	upstreamStatus := http.StatusOK
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/preflight") {
			t.Errorf("unexpected path %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(upstreamStatus)
		w.Write([]byte(`{"code":0,"data":{"currentPlan":"free"}}`))
	}))
	defer upstream.Close()
	if err := db.SetSetting("card_api_base", upstream.URL); err != nil {
		t.Fatal(err)
	}
	r := gin.New()
	r.POST("/preflight", PublicCDKPreflight)
	for _, tc := range []struct {
		code, session string
		stored        int
		status        int
	}{
		{"GROK-FIXTURE", "sso=synthetic-grok-credential", 0, 200},
		{"GROK-SPACES", "lang=en;  sso=synthetic-grok-credential", 0, 200},
		{"GROK-TAB", "lang=en;\tsso-rw=synthetic-grok-credential", 0, 200},
		{"GROK-FAILED", "lang=en;  sso=synthetic-grok-credential", 0, 401},
		{"X-FIXTURE", `{"auth_token":"fixture","ct0":"fixture","billing_email":"fixture@example.invalid"}`, 0, 200},
		{"GPT-FIXTURE", `{"sessionToken":"synthetic-gpt-session"}`, 1, 200},
	} {
		upstreamStatus = tc.status
		body, _ := json.Marshal(map[string]any{"code": tc.code, "credential": map[string]string{"mode": "session", "session": tc.session}})
		w := httptest.NewRecorder()
		req := httptest.NewRequest("POST", "/preflight", strings.NewReader(string(body)))
		req.Header.Set("Content-Type", "application/json")
		r.ServeHTTP(w, req)
		if w.Code != tc.status {
			t.Fatalf("preflight failed %d", w.Code)
		}
		var count int
		if err := c.QueryRow(`SELECT count(*) FROM cdk_session_bindings WHERE cdk_code=?`, tc.code).Scan(&count); err != nil {
			t.Fatal(err)
		}
		if count != tc.stored {
			t.Errorf("%s billing binding count=%d want=%d", tc.code, count, tc.stored)
		}
	}
}
