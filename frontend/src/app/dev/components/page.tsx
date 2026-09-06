"use client";

import { useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { Stepper } from "@/components/ui/stepper";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "@/components/ui/toast";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border p-4">{children}</div>
    </section>
  );
}

/** F1.1 primitives showcase (Storybook-equivalent). Toggle theme + RTL to verify each
 *  primitive in light/dark/RTL. */
export default function ComponentsShowcase() {
  const [rtl, setRtl] = useState(false);

  return (
    <div dir={rtl ? "rtl" : "ltr"} className="mx-auto max-w-4xl space-y-8 p-8">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Design system · F1.1</h1>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setRtl((v) => !v)}>
            {rtl ? "LTR" : "RTL"}
          </Button>
          <ThemeToggle />
        </div>
      </header>

      <Section title="Buttons">
        <Button>Default</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="outline">Outline</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="destructive">Destructive</Button>
        <Button variant="link">Link</Button>
        <Button disabled>Disabled</Button>
        <Button size="sm">Small</Button>
        <Button size="lg">Large</Button>
      </Section>

      <Section title="Inputs">
        <div className="grid w-full max-w-sm gap-2">
          <Label htmlFor="name">Name</Label>
          <Input id="name" placeholder="Jane Doe" />
          <Textarea placeholder="Notes…" />
          <Input aria-invalid placeholder="Invalid" />
        </div>
      </Section>

      <Section title="Selection controls">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox defaultChecked /> Checkbox
        </label>
        <label className="flex items-center gap-2 text-sm">
          <Switch defaultChecked /> Switch
        </label>
        <RadioGroup defaultValue="a" className="flex gap-4">
          <label className="flex items-center gap-2 text-sm">
            <RadioGroupItem value="a" /> A
          </label>
          <label className="flex items-center gap-2 text-sm">
            <RadioGroupItem value="b" /> B
          </label>
        </RadioGroup>
        <Select>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Pick one" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="open">Open</SelectItem>
            <SelectItem value="won">Won</SelectItem>
            <SelectItem value="lost">Lost</SelectItem>
          </SelectContent>
        </Select>
      </Section>

      <Section title="Overlays">
        <Dialog>
          <DialogTrigger asChild>
            <Button variant="outline">Dialog</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Dialog title</DialogTitle>
              <DialogDescription>An accessible modal dialog.</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button>Confirm</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline">Sheet</Button>
          </SheetTrigger>
          <SheetContent>
            <SheetHeader>
              <SheetTitle>Side panel</SheetTitle>
            </SheetHeader>
          </SheetContent>
        </Sheet>
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline">Popover</Button>
          </PopoverTrigger>
          <PopoverContent>Popover content</PopoverContent>
        </Popover>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button variant="outline">Tooltip</Button>
          </TooltipTrigger>
          <TooltipContent>Helpful hint</TooltipContent>
        </Tooltip>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline">Menu</Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuLabel>Actions</DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Edit</DropdownMenuItem>
            <DropdownMenuItem>Duplicate</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Button variant="outline" onClick={() => toast.success("Saved")}>
          Toast
        </Button>
      </Section>

      <Section title="Tabs">
        <Tabs defaultValue="fields" className="w-full">
          <TabsList>
            <TabsTrigger value="fields">Fields</TabsTrigger>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
          </TabsList>
          <TabsContent value="fields">Field content</TabsContent>
          <TabsContent value="timeline">Timeline content</TabsContent>
        </Tabs>
      </Section>

      <Section title="Data display">
        <Badge>Default</Badge>
        <Badge variant="success">Success</Badge>
        <Badge variant="warning">Warning</Badge>
        <Badge variant="destructive">Error</Badge>
        <Badge variant="outline">Outline</Badge>
        <Avatar>
          <AvatarFallback>JD</AvatarFallback>
        </Avatar>
        <Spinner />
        <Skeleton className="h-6 w-24" />
      </Section>

      <Section title="Table">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow>
              <TableCell>Acme</TableCell>
              <TableCell>
                <Badge variant="success">Open</Badge>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Section>

      <Section title="Stepper">
        <Stepper
          className="w-full"
          current={1}
          steps={[
            { id: "1", label: "Details" },
            { id: "2", label: "Fields" },
            { id: "3", label: "Review" },
          ]}
        />
      </Section>

      <Section title="States">
        <div className="grid w-full gap-3 sm:grid-cols-2">
          <EmptyState title="No records yet" description="Create your first record." />
          <ErrorState title="Something went wrong" action={{ label: "Retry", onClick: () => {} }} />
        </div>
      </Section>
    </div>
  );
}
