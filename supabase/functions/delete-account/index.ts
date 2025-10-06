// supabase/functions/delete-account/index.ts
// Suppression côté app : users_map -> users/"Users" -> Auth, avec SQL direct pour éviter les problèmes de casse.
// Nécessite les variables d'env: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import postgres from "https://deno.land/x/postgresjs/mod.js";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const anonKey = Deno.env.get("SUPABASE_ANON_KEY")!;
    const serviceRole = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
    const dbUrl = Deno.env.get("SUPABASE_DB_URL")!;
    if (!supabaseUrl || !anonKey || !serviceRole || !dbUrl) {
      throw new Error("Missing env vars");
    }

    // 1) Authentifier l'appelant (JWT de l'app)
    const userClient = createClient(supabaseUrl, anonKey, {
      global: { headers: { Authorization: req.headers.get("Authorization") ?? "" } },
    });
    const { data: { user }, error: userErr } = await userClient.auth.getUser();
    if (userErr || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401,
        headers: { "Content-Type": "application/json", ...corsHeaders },
      });
    }

    // 2) Connexion SQL directe (service role)
    const sql = postgres(dbUrl, { prepare: false });

    // 3) Récupérer l'id interne via users_map
    const mapRows =
      await sql/*sql*/`select user_id from public.users_map where auth_uid = ${user.id} limit 1`;
    const internalUserId: number | null = mapRows.length ? mapRows[0].user_id : null;

    let usersDeleted = 0;
    let usersMapDeleted = 0;

    if (internalUserId !== null) {
      // 4) Supprimer dans public.users (minuscule) OU public."Users" (Majuscules)
      // On tente d'abord public.users
      try {
        const del1 =
          await sql/*sql*/`delete from public.users where id = ${internalUserId} returning 1`;
        usersDeleted += del1.length;
      } catch (_) {
        // ignore, peut ne pas exister
      }
      // Puis on tente public."Users"
      try {
        const del2 =
          await sql/*sql*/`delete from public."Users" where id = ${internalUserId} returning 1`;
        usersDeleted += del2.length;
      } catch (_) {
        // ignore si n'existe pas
      }

      // 5) Supprimer le mapping
      const delMap =
        await sql/*sql*/`delete from public.users_map where auth_uid = ${user.id} returning 1`;
      usersMapDeleted += delMap.length;
    }

    // 6) Supprimer le compte Auth (révoque les sessions)
    const admin = createClient(supabaseUrl, serviceRole);
    const { error: delAuthErr } = await admin.auth.admin.deleteUser(user.id);
    if (delAuthErr) throw delAuthErr;

    // 7) Fermer proprement la connexion SQL
    await sql.end();

    return new Response(
      JSON.stringify({
        ok: true,
        authDeleted: true,
        usersDeleted,
        usersMapDeleted,
      }),
      { status: 200, headers: { "Content-Type": "application/json", ...corsHeaders } }
    );
  } catch (e) {
    console.error(e);
    const message = e instanceof Error ? e.message : String(e);
    return new Response(JSON.stringify({ error: "Deletion failed", message }), {
      status: 500,
      headers: { "Content-Type": "application/json", ...corsHeaders },
    });
  }
});
