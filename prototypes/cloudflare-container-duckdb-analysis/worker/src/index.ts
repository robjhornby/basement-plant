import { Container, getContainer } from "@cloudflare/containers";

export class AnalysisContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "2m";
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("POST /run to start the prototype analysis container\n", {
        status: 405,
      });
    }

    const container = getContainer(env.ANALYSIS_CONTAINER, "daily-analysis");
    return container.fetch("http://container/run", {
      method: "POST",
      body: await request.text(),
    });
  },
};

interface Env {
  ANALYSIS_CONTAINER: DurableObjectNamespace;
}

