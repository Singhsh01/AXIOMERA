"use client";
import { createContext, useContext } from "react";

export type Me = { id: string; name: string; role: string; permissions: string[]; workspace: { id: string; name: string } };
export const MeCtx = createContext<Me | null>(null);
export const useMe = () => useContext(MeCtx);
export const can = (me: Me | null, p: string) => !!me?.permissions.includes(p);
